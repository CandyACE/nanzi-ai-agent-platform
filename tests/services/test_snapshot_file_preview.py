"""审核快照文件预览的安全边界测试。

背景：审核面板此前只渲染 ``SKILL.md``，技能包里的 ``scripts/*.py`` 等可执行文件
在无人查看的情况下就能被「通过并发布」进公共技能库，而界面文案却承诺
「审查文件 Diff 与代码合规性」。补上包内文件浏览后，这条读取路径必须自己把关：
它由 ``element:skills:admin`` 用户触发，输入完全来自请求参数。
"""
from __future__ import annotations

import pytest

from app.services.skill_publication_service import (
    SNAPSHOT_PREVIEW_MAX_BYTES,
    SnapshotFileError,
    read_snapshot_text_file,
    resolve_snapshot_file,
)

pytestmark = pytest.mark.no_infrastructure


@pytest.fixture
def snapshot(tmp_path):
    """构造一个带子目录的快照。"""
    root = tmp_path / "snapshots" / "pub-1"
    (root / "scripts").mkdir(parents=True)
    (root / "SKILL.md").write_text("# 技能\n", encoding="utf-8")
    (root / "scripts" / "run.py").write_text("print('hi')\n", encoding="utf-8")
    return root


def test_reads_nested_script(snapshot):
    assert read_snapshot_text_file(str(snapshot), "scripts/run.py") == "print('hi')\n"
    assert read_snapshot_text_file(str(snapshot), "SKILL.md") == "# 技能\n"


def test_resolves_to_path_inside_snapshot(snapshot):
    resolved = resolve_snapshot_file(str(snapshot), "scripts/run.py")
    assert resolved.startswith(str(snapshot))


@pytest.mark.parametrize(
    "bad_path",
    [
        "../outside.md",              # 父目录穿越
        "scripts/../../../etc/hosts",  # 多层穿越
        "",
        "   ",
    ],
)
def test_rejects_traversal_and_empty(snapshot, bad_path):
    with pytest.raises(SnapshotFileError):
        resolve_snapshot_file(str(snapshot), bad_path)


def test_rejects_absolute_path(snapshot, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(SnapshotFileError):
        resolve_snapshot_file(str(snapshot), str(outside))


def test_rejects_symlink_escape(snapshot, tmp_path):
    """软链接指向快照外也必须被拒（realpath 解析后再比对前缀）。"""
    outside = tmp_path / "secret.md"
    outside.write_text("secret", encoding="utf-8")
    link = snapshot / "link.md"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):  # pragma: no cover - 平台不支持符号链接
        pytest.skip("当前平台不支持创建符号链接")

    with pytest.raises(SnapshotFileError):
        resolve_snapshot_file(str(snapshot), "link.md")


def test_rejects_non_text_extension(snapshot):
    (snapshot / "payload.bin").write_bytes(b"\x00\x01\x02")
    with pytest.raises(SnapshotFileError):
        resolve_snapshot_file(str(snapshot), "payload.bin")


def test_rejects_oversized_file(snapshot):
    (snapshot / "huge.md").write_text("x" * (SNAPSHOT_PREVIEW_MAX_BYTES + 1), encoding="utf-8")
    with pytest.raises(SnapshotFileError):
        resolve_snapshot_file(str(snapshot), "huge.md")


def test_rejects_missing_file_and_missing_root(snapshot, tmp_path):
    with pytest.raises(SnapshotFileError):
        resolve_snapshot_file(str(snapshot), "scripts/nope.py")
    with pytest.raises(SnapshotFileError):
        resolve_snapshot_file(str(tmp_path / "does-not-exist"), "SKILL.md")
    with pytest.raises(SnapshotFileError):
        resolve_snapshot_file("", "SKILL.md")


def test_directory_is_not_a_readable_file(snapshot):
    """目录本身不能被当作文件读取。"""
    with pytest.raises(SnapshotFileError):
        resolve_snapshot_file(str(snapshot), "scripts")
