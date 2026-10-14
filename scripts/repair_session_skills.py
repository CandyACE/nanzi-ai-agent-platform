#!/usr/bin/env python
"""会话技能快照维护：断开硬链接、回收陈旧快照。

会话目录 ``<user_key>/sessions/<cid>/skills`` 是**派生物**：平台每次构建工作区都会按需重新
铺设（``_preseed_session_skills`` 把技能铺进 ``skills/.seed``，账本写在会话根
``.session_skills.json``），删掉只会在下次对话时自动重建。因此这里提供两个安全的维护动作：

1. ``--relink``：把仍是硬链接（``st_nlink > 1``）的技能文件替换为独立副本。
   历史版本用 ``os.link`` 铺设快照，从快照写入会顺着共享 inode 改到平台技能源（影响所有
   用户）；代码现已改为真实复制，但存量文件仍需就地断开。
2. ``--prune-stale DAYS``：删除「技能目录与其会话目录都超过 DAYS 天未修改」的会话技能
   快照（连平台账本一起清掉），纯粹回收磁盘；下次对话会重建。技能内容更新后遗留的
   ``<name>_1`` 旧副本也会随之清除。

默认 **dry-run**：只有显式加 ``--apply`` 才会真正改动文件。

示例::

    python scripts/repair_session_skills.py --relink                 # 预览
    python scripts/repair_session_skills.py --relink --apply
    python scripts/repair_session_skills.py --prune-stale 30         # 预览
    python scripts/repair_session_skills.py --prune-stale 30 --apply
    python scripts/repair_session_skills.py --user admin__1 --relink --apply
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
import time

SKILLS_DIR_NAME = "skills"
SESSIONS_DIR_NAME = "sessions"
#: 平台快照目录（AgentScope 的 seed 模板）。老会话可能还是平铺布局，见
#: ``session_skill_snapshot_dir``。
SEED_DIR_NAME = ".seed"
#: 平台账本，位于会话根（刻意不在 ``skills/`` 里，否则会被 AgentScope 当技能条目处理）。
LEDGER_NAME = ".session_skills.json"
SECONDS_PER_DAY = 86400


def resolve_default_root() -> str:
    """平台默认的用户工作区根目录（与 ``app.utils.fs_access`` 保持一致）。"""
    env_root = os.environ.get("AGENTSCOPE_WORKSPACE_HOST_ROOT")
    if env_root:
        return env_root
    data_dir = "/app/data" if os.path.isdir("/app/data") else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
    )
    return os.path.join(data_dir, "agent_workspaces")


def iter_session_skill_dirs(user_root: str):
    """逐个产出 ``(session_dir, skills_dir)``。"""
    sessions_dir = os.path.join(user_root, SESSIONS_DIR_NAME)
    if not os.path.isdir(sessions_dir):
        return
    for conversation_id in sorted(os.listdir(sessions_dir)):
        session_dir = os.path.join(sessions_dir, conversation_id)
        skills_dir = os.path.join(session_dir, SKILLS_DIR_NAME)
        if os.path.isdir(skills_dir):
            yield session_dir, skills_dir


def session_skill_snapshot_dir(skills_dir: str) -> str:
    """技能快照实际所在的目录。

    平台现在的布局是 ``skills/.seed``；更早的会话是平铺在 ``skills/`` 根下——对后者直接
    回退到 ``skills/``，这样维护动作对两种布局都有效。
    """
    seed_dir = os.path.join(skills_dir, SEED_DIR_NAME)
    return seed_dir if os.path.isdir(seed_dir) else skills_dir


def session_skills_ledger_path(session_dir: str) -> str:
    return os.path.join(session_dir, LEDGER_NAME)


def directory_size(path: str) -> int:
    """目录内普通文件的**名义**大小（硬链接会重复计数，仅用于展示量级）。"""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path, followlinks=False):
        for filename in filenames:
            try:
                total += os.lstat(os.path.join(dirpath, filename)).st_size
            except OSError:
                continue
    return total


def relink_skill_files(skills_dir: str, *, apply: bool) -> tuple[int, int]:
    """断开会话技能副本里的硬链接，返回 ``(硬链接文件数, 已断开数)``。"""
    linked = 0
    fixed = 0
    for dirpath, _dirnames, filenames in os.walk(skills_dir, followlinks=False):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            try:
                file_stat = os.lstat(path)
            except OSError:
                continue
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink <= 1:
                continue
            linked += 1
            if not apply:
                continue
            temp_path = f"{path}.relink-tmp"
            try:
                shutil.copy2(path, temp_path)
                os.replace(temp_path, path)
                fixed += 1
            except OSError as exc:
                print(f"    ! 断开失败 {path}: {exc}", file=sys.stderr)
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
    return linked, fixed


def prune_stale_session_skills(
    user_root: str, *, older_than_days: int, apply: bool
) -> tuple[int, int, int]:
    """删除陈旧会话技能快照，返回 ``(候选会话数, 已删除数, 回收字节)``。"""
    cutoff = time.time() - older_than_days * SECONDS_PER_DAY
    candidates = 0
    removed = 0
    freed_bytes = 0
    for session_dir, skills_dir in iter_session_skill_dirs(user_root):
        snapshot_dir = session_skill_snapshot_dir(skills_dir)
        try:
            newest = max(os.path.getmtime(session_dir), os.path.getmtime(skills_dir))
        except OSError:
            continue
        if newest >= cutoff:
            continue
        candidates += 1
        size = directory_size(skills_dir)
        print(
            f"    候选 {snapshot_dir}"
            f"（最后修改 {time.strftime('%Y-%m-%d %H:%M', time.localtime(newest))}，"
            f"{size / 1024:.0f}K）"
        )
        if not apply:
            continue
        try:
            shutil.rmtree(skills_dir)
        except OSError as exc:
            print(f"    ! 删除失败 {skills_dir}: {exc}", file=sys.stderr)
            continue
        ledger_path = session_skills_ledger_path(session_dir)
        if os.path.isfile(ledger_path):
            try:
                os.remove(ledger_path)
            except OSError as exc:
                print(f"    ! 账本删除失败 {ledger_path}: {exc}", file=sys.stderr)
        removed += 1
        freed_bytes += size
    return candidates, removed, freed_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="会话技能副本维护（默认 dry-run，加 --apply 才真正改动）",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="用户工作区根目录（默认取平台配置或 AGENTSCOPE_WORKSPACE_HOST_ROOT）",
    )
    parser.add_argument("--user", default=None, help="只处理指定 user_key 目录")
    parser.add_argument(
        "--relink",
        action="store_true",
        help="把会话技能副本里的硬链接文件替换为独立副本",
    )
    parser.add_argument(
        "--prune-stale",
        type=int,
        metavar="DAYS",
        default=0,
        help="删除超过 DAYS 天未修改的会话技能快照",
    )
    parser.add_argument("--apply", action="store_true", help="真正执行（默认只预览）")
    args = parser.parse_args(argv)

    if not args.relink and args.prune_stale <= 0:
        parser.print_help()
        return 1

    root = os.path.abspath(args.root or resolve_default_root())
    if not os.path.isdir(root):
        print(f"工作区根目录不存在: {root}", file=sys.stderr)
        return 1

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] 工作区根目录: {root}")
    if args.prune_stale > 0:
        print(f"[{mode}] 将清理最后修改早于 {args.prune_stale} 天的会话技能快照")

    user_keys = (
        [args.user] if args.user else sorted(os.listdir(root))
    )
    totals = {"sessions": 0, "linked": 0, "fixed": 0, "pruned": 0, "freed": 0}

    for user_key in user_keys:
        user_root = os.path.join(root, user_key)
        if not os.path.isdir(user_root):
            continue
        session_dirs = list(iter_session_skill_dirs(user_root))
        if not session_dirs:
            continue
        print(f"\n用户 {user_key}: {len(session_dirs)} 个会话技能目录")
        totals["sessions"] += len(session_dirs)

        if args.relink:
            for _session_dir, skills_dir in session_dirs:
                snapshot_dir = session_skill_snapshot_dir(skills_dir)
                linked, fixed = relink_skill_files(snapshot_dir, apply=args.apply)
                totals["linked"] += linked
                totals["fixed"] += fixed
                if linked:
                    print(f"    {snapshot_dir}: 硬链接 {linked} 个文件")

        if args.prune_stale > 0:
            candidates, removed, freed = prune_stale_session_skills(
                user_root, older_than_days=args.prune_stale, apply=args.apply
            )
            if not candidates:
                print("    没有符合条件的陈旧快照")
            totals["pruned"] += removed
            totals["freed"] += freed

    print("\n=== 汇总 ===")
    print(f"扫描会话技能目录: {totals['sessions']}")
    if args.relink:
        print(
            f"硬链接文件: {totals['linked']}，已断开: {totals['fixed']}"
            + ("（dry-run 未改动）" if not args.apply else "")
        )
    if args.prune_stale > 0:
        print(
            f"陈旧快照已删除: {totals['pruned']}，回收 ≈ {totals['freed'] / 1024 / 1024:.1f}M"
            + ("（dry-run 未改动）" if not args.apply else "")
        )
    if not args.apply:
        print("\n这是预览结果，加 --apply 才会真正执行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
