"""API 工具「粘贴请求」解析契约。

静态断言只能证明代码长什么样，证明不了「解析会不会把用户的请求读错」——
所以核心行为用 ``node`` 真跑一遍纯函数（照 ``tool_schema_roundtrip.mjs`` 的先例）。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

IMPORT_UTIL = Path("frontend/src/utils/toolImport.ts")
ROUNDTRIP = Path("tests/frontend/tool_import_roundtrip.mjs")


def _source(path: Path) -> str:
    if not path.exists():
        pytest.fail(f"缺少文件：{path}")
    return path.read_text(encoding="utf-8")


def test_import_util_never_throws():
    """解析失败必须是返回值，不是异常——界面上要原地提示并保留用户原文。"""
    source = _source(IMPORT_UTIL)
    assert "export const parseRequestInput" in source
    assert "ParseFailure" in source


def test_import_util_covers_url_and_curl():
    source = _source(IMPORT_UTIL)
    assert "parseCurl" in source
    assert "tokenizeShellLike" in source
    for flag in ("-X", "--request", "-H", "--header", "--url"):
        assert flag in source, f"curl 解析缺少 {flag}"


def test_import_util_uses_extensions_for_node_execution():
    """本模块会被 node 直接执行，跨文件导入必须带 .ts 扩展名。"""
    source = _source(IMPORT_UTIL)
    assert "from './toolMethods.ts'" in source, (
        "Node 的 ESM 解析不做扩展名补全，缺了 .ts 会让往返测试报 ERR_MODULE_NOT_FOUND"
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node 才能执行纯函数往返测试")
def test_import_roundtrip_behaviour_via_node():
    assert ROUNDTRIP.exists(), "往返测试脚本缺失"
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", str(ROUNDTRIP)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "工具导入往返测试全部通过" in proc.stdout


DRAFT_UTIL = Path("frontend/src/utils/toolDraft.ts")
DRAFT_ROUNDTRIP = Path("tests/frontend/tool_draft_roundtrip.mjs")


def test_draft_util_keeps_location_rules_in_sync_with_runtime():
    """落位规则是「试跑能过、运行时调不通」的唯一防线，必须写死在这里。"""
    source = _source(DRAFT_UTIL)
    assert "resolveParamLocation" in source
    assert "export const buildDraftParams" in source
    assert "export const buildDraftSchema" in source
    # 序列化必须复用 toolSchema，不得自己拼 JSON
    assert "serializeToolSchema" in source


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node 才能执行纯函数往返测试")
def test_draft_roundtrip_behaviour_via_node():
    assert DRAFT_ROUNDTRIP.exists(), "往返测试脚本缺失"
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", str(DRAFT_ROUNDTRIP)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "工具草稿往返测试全部通过" in proc.stdout
