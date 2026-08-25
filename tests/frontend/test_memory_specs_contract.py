from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_memory_management_specs_modal_contract():
    view = _source("frontend/src/views/MemoryManagement.vue")

    # 1. 验证 ? 号按钮与状态定义
    assert "showSpecsModal" in view
    assert "activeSpecsTab" in view
    assert "记忆系统设计规范与使用指南" in view

    # 2. 验证三大 Tab 核心技术概念
    assert "核心架构与数据流" in view or "Architecture & Data Flow" in view
    assert "数据生成机制与参数" in view or "Generation & Parameters" in view
    assert "记忆检索与最佳实践" in view or "Retrieval & Best Practice" in view
    assert "跨会话长期记忆" in view
    assert "nanzi:idx:memory:session_summary" in view
    assert "memory_summarize_debounce_turns" in view
