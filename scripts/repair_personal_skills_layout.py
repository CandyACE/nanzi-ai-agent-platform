#!/usr/bin/env python
"""个人技能源布局修复：把历史遗留的 ``.seed`` 目录搬回规范平铺布局。

背景
----
K8s 沙箱在补齐技能子挂载之前只挂载了整个用户工作区，于是 AgentScope 的技能根
``${workdir}/skills`` 恰好**就是个人技能源目录** ``<user_key>/skills``；它
``initialize()`` 时的布局迁移会把平铺技能**搬移**（``shutil.move``）进
``<user_key>/skills/.seed/<skill_id>/``。

平台所有主机侧枚举都会跳过点开头目录，于是这些技能在「技能列表
（``list_available_skills``）」「个人技能中心」「工作台个人技能计数」「资源目录」里
**集体隐形**——技能并没有丢，只是躺进了 ``.seed``。

代码侧现已兼容读取两种布局（见 ``app/services/ai/skill_resolver.py`` 的
``iter_personal_skill_dirs`` / ``resolve_personal_skill_dir``），本脚本负责把**存量数据**
搬回规范布局。

动作
----
``<user_key>/skills/.seed/<skill_id>`` → ``<user_key>/skills/<skill_id>``

* 默认 **dry-run**，只有显式加 ``--apply`` 才真正改动文件；
* 目标已存在同名技能时**跳过并报告冲突**，绝不覆盖；
* 缺 ``SKILL.md`` 的目录按非技能残留处理，保守跳过；
* 搬空后的 ``.seed`` 目录会被移除（仅当它确实为空）；
* 幂等：可重复执行。

示例::

    python scripts/repair_personal_skills_layout.py                    # 预览
    python scripts/repair_personal_skills_layout.py --apply
    python scripts/repair_personal_skills_layout.py --user admin__1 --apply
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

SKILLS_DIR_NAME = "skills"
#: AgentScope 的 seed 布局目录名，见 ``app/services/ai/skill_resolver.py``。
SEED_DIR_NAME = ".seed"


def resolve_default_root() -> str:
    """平台默认的用户工作区根目录（与 ``app.utils.fs_access`` 保持一致）。"""
    env_root = os.environ.get("AGENTSCOPE_WORKSPACE_HOST_ROOT")
    if env_root:
        return env_root
    data_dir = "/app/data" if os.path.isdir("/app/data") else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
    )
    return os.path.join(data_dir, "agent_workspaces")


def iter_seed_skill_dirs(personal_root: str):
    """产出个人技能源 ``.seed`` 下的 ``(skill_id, seed_skill_dir)``。"""
    seed_dir = os.path.join(personal_root, SEED_DIR_NAME)
    if not os.path.isdir(seed_dir):
        return
    for name in sorted(os.listdir(seed_dir)):
        if name.startswith("."):
            continue
        path = os.path.join(seed_dir, name)
        if os.path.isdir(path):
            yield name, path


def repair_user(personal_root: str, *, apply: bool) -> dict[str, int]:
    """把单个用户个人技能源里的 ``.seed`` 技能搬回平铺位置。"""
    stats = {"moved": 0, "conflict": 0, "skipped": 0}
    for skill_id, seed_path in iter_seed_skill_dirs(personal_root):
        target = os.path.join(personal_root, skill_id)
        if os.path.exists(target):
            stats["conflict"] += 1
            print(f"    冲突跳过（平铺已存在同名技能，需人工确认）: {skill_id}")
            continue
        if not os.path.isfile(os.path.join(seed_path, "SKILL.md")):
            stats["skipped"] += 1
            print(f"    跳过（缺 SKILL.md，疑似非技能残留）: {skill_id}")
            continue
        print(f"    搬回: {SEED_DIR_NAME}/{skill_id} -> {skill_id}")
        if apply:
            shutil.move(seed_path, target)
        stats["moved"] += 1

    if apply:
        seed_dir = os.path.join(personal_root, SEED_DIR_NAME)
        try:
            if os.path.isdir(seed_dir) and not os.listdir(seed_dir):
                os.rmdir(seed_dir)
                print(f"    已移除空目录: {SEED_DIR_NAME}/")
        except OSError:
            pass
    return stats


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
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root or resolve_default_root())
    if not os.path.isdir(root):
        print(f"工作区根目录不存在: {root}", file=sys.stderr)
        return 1

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] 工作区根目录: {root}")

    user_keys = [args.user] if args.user else sorted(os.listdir(root))
    totals = {"users": 0, "moved": 0, "conflict": 0, "skipped": 0}
    for user_key in user_keys:
        personal_root = os.path.join(root, user_key, SKILLS_DIR_NAME)
        if not os.path.isdir(os.path.join(personal_root, SEED_DIR_NAME)):
            continue
        totals["users"] += 1
        print(f"  {user_key}:")
        stats = repair_user(personal_root, apply=args.apply)
        for key, value in stats.items():
            totals[key] += value

    print(
        f"[{mode}] 完成：涉及用户 {totals['users']}，"
        f"待搬回/已搬回 {totals['moved']}，冲突跳过 {totals['conflict']}，"
        f"非技能跳过 {totals['skipped']}"
    )
    if not args.apply and totals["moved"]:
        print("提示：以上为预览结果，确认无误后加 --apply 正式执行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
