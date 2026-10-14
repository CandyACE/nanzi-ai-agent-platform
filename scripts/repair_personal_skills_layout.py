#!/usr/bin/env python
"""个人技能源布局修复：把历史遗留的 ``.seed`` 目录搬回规范平铺布局。

背景
----
K8s 沙箱在补齐技能子挂载之前只挂载了整个用户工作区，于是 AgentScope 的技能根
``${workdir}/skills`` 恰好**就是个人技能源目录** ``<user_key>/skills``；它
``initialize()`` 时的布局迁移会把平铺技能**搬移**进
``<user_key>/skills/.seed/<skill_id>/``。

平台的主机侧枚举都会跳过点开头目录，于是这些技能在「技能列表
（``list_available_skills``）」「个人技能中心」「工作台个人技能计数」「资源目录」里
**集体隐形**——技能并没有丢，只是躺进了 ``.seed``。

代码侧现已兼容读取两种布局（见 ``app/services/ai/skill_resolver.py`` 的
``iter_personal_skill_dirs`` / ``resolve_personal_skill_dir``），本脚本负责把**存量数据**
搬回规范布局。

动作
----
``<user_key>/skills/.seed/<skill_id>`` → ``<user_key>/skills/<skill_id>``

安全约定
--------
* 默认 **dry-run**，只有显式加 ``--apply`` 才真正改动文件；
* 与**公共技能同 ID** 的目录**默认拒绝搬移**：旧的 ``.seed`` 是 AgentScope 把
  ``skill_paths``（公共 + 个人）整体打包的产物，因此里面可能混有公共技能副本；
  一旦搬成个人技能，平台的「同 ID 个人优先」会把这些公共技能**冻结**成该用户的
  私有旧版，公共技能后续更新对他永久失效。读不到公共技能库时同样默认拒绝
  （fail-closed），可用 ``--allow-platform-ids`` 显式放行；
* 技能 ID 不符合平台正则（``^[a-zA-Z0-9_-]+$``）的目录跳过：搬过去平台也读不到；
* 缺 ``SKILL.md`` 的目录按非技能残留处理，保守跳过；
* 目标已存在同名技能时**跳过并报告冲突**，绝不覆盖（用 ``os.rename`` 做原子断言，
  避免并发下把技能移进目标目录内部变成 ``X/X``）；
* 搬空后的 ``.seed`` 会被移除；若里面还剩点开头的 AgentScope 内部文件（如
  ``.index``），仅在显式 ``--prune-remaining`` 时才清理，否则如实报告残留；
* 幂等：可重复执行。

与 ``scripts/repair_session_skills.py`` 的关系
--------------------------------------------
两者命名/参数风格一致，但**布局方向相反且都是正确的**：那个脚本处理会话技能快照，
其规范布局就是 ``.seed``（seed 优先、回退平铺）；本脚本处理个人技能源，规范布局是
平铺（平铺优先、回退 seed）。故本脚本的常量命名为 ``LEGACY_SEED_DIR_NAME``。

示例::

    python scripts/repair_personal_skills_layout.py                    # 预览
    python scripts/repair_personal_skills_layout.py --apply
    python scripts/repair_personal_skills_layout.py --user admin__1 --apply
"""

from __future__ import annotations

import argparse
import os
import re
import sys

SKILLS_DIR_NAME = "skills"
#: 个人技能源里**历史遗留**的 seed 目录名（注意与 repair_session_skills.py 的
#: SEED_DIR_NAME 同名但语义相反，见模块 docstring 末尾）。
LEGACY_SEED_DIR_NAME = ".seed"
#: 与 ``app/services/ai/skill_resolver.py::_validate_skill_id`` 保持一致。
SKILL_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def resolve_default_root() -> str:
    """平台默认的用户工作区根目录（与 ``app.utils.fs_access`` 保持一致）。"""
    env_root = os.environ.get("AGENTSCOPE_WORKSPACE_HOST_ROOT")
    if env_root:
        return env_root
    data_dir = "/app/data" if os.path.isdir("/app/data") else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
    )
    return os.path.join(data_dir, "agent_workspaces")


def resolve_platform_skills_dir(explicit: str | None = None) -> str | None:
    """公共技能库位置，口径与平台 ``app/core/config.py`` 的 ``SKILLS_DIR`` **保持一致**。

    注意：平台的 ``SKILLS_DIR`` 是只看路径存在性的 ``@property``，**不读 ``SKILLS_DIR``
    环境变量**。脚本必须同口径，否则 fail-closed 可能基于错误的公共技能清单（既可能误拒
    合法搬移，也可能漏拒真副本）。要指向别处请显式传 ``--platform-skills-dir``。
    """
    if explicit:
        return os.path.abspath(explicit)
    container_path = "/app/data/skills"
    if os.path.isdir(container_path):
        return container_path
    host_path = os.path.expanduser("~/.agents/skills")
    if os.path.isdir(host_path):
        # 平台在回退时还会 makedirs，这里只读不改，目标是"判定清单"
        return host_path
    return None


def platform_skill_ids(platform_dir: str | None) -> set[str] | None:
    """公共技能 ID 集合；返回 ``None`` 表示**无法判定**（调用方须 fail-closed）。

    目录存在但为空 → 返回空集合（这是"公共库确实为空"的合法状态）。
    """
    if not platform_dir or not os.path.isdir(platform_dir):
        return None
    try:
        return {
            name
            for name in os.listdir(platform_dir)
            if not name.startswith(".") and os.path.isdir(os.path.join(platform_dir, name))
        }
    except OSError:
        return None


def iter_seed_skill_dirs(personal_root: str):
    """产出个人技能源 ``.seed`` 下的 ``(skill_id, seed_skill_dir)``（仅目录）。"""
    seed_dir = os.path.join(personal_root, LEGACY_SEED_DIR_NAME)
    if not os.path.isdir(seed_dir):
        return
    try:
        names = sorted(os.listdir(seed_dir))
    except OSError:
        return
    for name in names:
        if name.startswith("."):
            continue
        path = os.path.join(seed_dir, name)
        if os.path.isdir(path):
            yield name, path


def _seed_remaining_entries(personal_root: str) -> list[str]:
    seed_dir = os.path.join(personal_root, LEGACY_SEED_DIR_NAME)
    try:
        return sorted(os.listdir(seed_dir))
    except OSError:
        return []


def repair_user(
    personal_root: str,
    *,
    apply: bool,
    platform_ids: set[str] | None,
    allow_platform_ids: bool,
    prune_remaining: bool,
) -> tuple[dict[str, int], list[str]]:
    """把单个用户个人技能源里的 ``.seed`` 技能搬回平铺位置。

    返回 ``(统计, 未搬移条目清单)``。
    """
    stats = {"moved": 0, "conflict": 0, "skipped": 0, "failed": 0}
    unhandled: list[str] = []

    for skill_id, seed_path in iter_seed_skill_dirs(personal_root):
        # ① 技能 ID 不合法：平台按正则识别技能，搬过去依然读不到，白搬且更乱
        if not SKILL_ID_PATTERN.match(skill_id):
            stats["skipped"] += 1
            unhandled.append(skill_id)
            print(f"    跳过（技能 ID 不符合平台规范，搬回也不可见）: {skill_id}")
            continue

        # ② 与公共技能同 ID：默认拒绝（见模块 docstring）
        if not allow_platform_ids:
            if platform_ids is None:
                stats["skipped"] += 1
                unhandled.append(skill_id)
                print(
                    f"    拒绝搬移（无法确认公共技能库清单，fail-closed）: {skill_id}"
                    "  ← 可用 --platform-skills-dir 指定，或 --allow-platform-ids 强制"
                )
                continue
            if skill_id in platform_ids:
                stats["skipped"] += 1
                unhandled.append(skill_id)
                print(
                    f"    拒绝搬移（与公共技能同 ID，疑为历史遗留副本，搬了会冻结公共技能更新）: {skill_id}"
                    "  ← 确认无误可用 --allow-platform-ids 强制"
                )
                continue

        # ③ 缺 SKILL.md：非技能残留
        if not os.path.isfile(os.path.join(seed_path, "SKILL.md")):
            stats["skipped"] += 1
            unhandled.append(skill_id)
            print(f"    跳过（缺 SKILL.md，疑似非技能残留）: {skill_id}")
            continue

        target = os.path.join(personal_root, skill_id)
        if os.path.exists(target):
            stats["conflict"] += 1
            print(f"    冲突跳过（平铺已存在同名技能，需人工确认）: {skill_id}")
            continue

        print(f"    搬回: {LEGACY_SEED_DIR_NAME}/{skill_id} -> {skill_id}")
        if apply:
            try:
                # os.rename 同文件系统内是原子的，且目标已存在会抛 OSError；
                # 不能用 shutil.move——目标若在检查之后被并发创建，它会把整个
                # 技能目录塞进目标内部（变成 X/X），造成技能"消失"。
                os.rename(seed_path, target)
            except OSError as exc:
                stats["failed"] += 1
                print(f"      失败（已跳过，源文件保持原位）: {exc}")
                continue
        stats["moved"] += 1

    seed_dir = os.path.join(personal_root, LEGACY_SEED_DIR_NAME)
    if not os.path.isdir(seed_dir):
        return stats, unhandled

    remaining = _seed_remaining_entries(personal_root)
    if not remaining:
        if apply:
            try:
                os.rmdir(seed_dir)
                print(f"    已移除空目录: {LEGACY_SEED_DIR_NAME}/")
            except OSError as exc:
                print(f"    空目录移除失败: {exc}")
        return stats, unhandled

    if prune_remaining:
        # 只清点开头的 AgentScope 内部文件（如 .index）；不带 SKILL.md 的普通目录
        # 可能是用户自己的内容，一律不碰。
        if apply:
            for entry in remaining:
                if not entry.startswith("."):
                    continue
                path = os.path.join(seed_dir, entry)
                try:
                    os.remove(path)
                    print(f"    已清理内部残留文件: {LEGACY_SEED_DIR_NAME}/{entry}")
                except OSError as exc:
                    print(f"    内部残留文件清理失败 {entry}: {exc}")
            remaining = _seed_remaining_entries(personal_root)
            if not remaining:
                try:
                    os.rmdir(seed_dir)
                    print(f"    已移除目录: {LEGACY_SEED_DIR_NAME}/")
                except OSError as exc:
                    print(f"    目录移除失败: {exc}")
                return stats, unhandled

    print(
        f"    注意：{LEGACY_SEED_DIR_NAME}/ 未移除，仍有未搬移条目（技能读取会同时兼容两种布局）:"
        f" {', '.join(remaining)}"
    )
    return stats, unhandled


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="个人技能源 .seed 布局修复（默认 dry-run，加 --apply 才真正改动）",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="用户工作区根目录（默认取平台配置或 AGENTSCOPE_WORKSPACE_HOST_ROOT）",
    )
    parser.add_argument("--user", default=None, help="只处理指定 user_key 目录")
    parser.add_argument("--apply", action="store_true", help="真正执行（默认只预览）")
    parser.add_argument(
        "--platform-skills-dir",
        default=None,
        help="公共技能库目录（默认按 SKILLS_DIR 环境变量 / data/skills / ~/.agents/skills 探测）",
    )
    parser.add_argument(
        "--allow-platform-ids",
        action="store_true",
        help="允许搬移与公共技能同 ID 的目录（默认拒绝，风险见脚本 docstring）",
    )
    parser.add_argument(
        "--prune-remaining",
        action="store_true",
        help="搬完后清理 .seed 里的点开头内部文件（如 .index），以便移除该目录",
    )
    args = parser.parse_args(argv)

    root_source = "--root" if args.root else (
        "AGENTSCOPE_WORKSPACE_HOST_ROOT" if os.environ.get("AGENTSCOPE_WORKSPACE_HOST_ROOT")
        else "默认 data/agent_workspaces"
    )
    root = os.path.abspath(args.root or resolve_default_root())
    if not os.path.isdir(root):
        print(f"工作区根目录不存在: {root}", file=sys.stderr)
        return 1

    platform_dir = resolve_platform_skills_dir(args.platform_skills_dir)
    platform_ids = platform_skill_ids(platform_dir)
    if args.allow_platform_ids:
        platform_desc = f"{platform_dir}（已显式放行同 ID 搬移）"
    elif platform_ids is None:
        platform_desc = f"未探测到（{platform_dir or '无候选目录'}）→ 默认拒绝所有搬移"
    else:
        platform_desc = f"{platform_dir}（{len(platform_ids)} 个技能 ID）"

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] 工作区根目录: {root}   (来源: {root_source})")
    print(f"[{mode}] 公共技能库: {platform_desc}")
    if args.apply:
        print(f"[{mode}] 提示：请先停服再执行（避免与正在运行的会话写入竞争）。")

    user_keys = [args.user] if args.user else sorted(os.listdir(root))
    totals = {"users": 0, "moved": 0, "conflict": 0, "skipped": 0, "failed": 0}
    all_unhandled: list[str] = []
    for user_key in user_keys:
        personal_root = os.path.join(root, user_key, SKILLS_DIR_NAME)
        if not os.path.isdir(os.path.join(personal_root, LEGACY_SEED_DIR_NAME)):
            continue
        totals["users"] += 1
        print(f"  {user_key}:")
        try:
            stats, unhandled = repair_user(
                personal_root,
                apply=args.apply,
                platform_ids=platform_ids,
                allow_platform_ids=args.allow_platform_ids,
                prune_remaining=args.prune_remaining,
            )
        except Exception as exc:  # noqa: BLE001 — 单个用户失败不应中断整轮
            totals["failed"] += 1
            print(f"    处理失败（继续下一个用户）: {exc}")
            continue
        for key, value in stats.items():
            totals[key] += value
        all_unhandled.extend(f"{user_key}/{name}" for name in unhandled)

    print(
        f"[{mode}] 完成：涉及用户 {totals['users']}，"
        f"待搬回/已搬回 {totals['moved']}，冲突跳过 {totals['conflict']}，"
        f"未搬移（非法名/公共同 ID/非技能残留/无法判定）{totals['skipped']}，"
        f"失败 {totals['failed']}"
    )
    if all_unhandled:
        print(f"[{mode}] 未搬移条目: {', '.join(all_unhandled[:20])}"
              + (" …" if len(all_unhandled) > 20 else ""))
    if not args.apply and totals["moved"]:
        print("提示：以上为预览结果，确认无误后加 --apply 正式执行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
