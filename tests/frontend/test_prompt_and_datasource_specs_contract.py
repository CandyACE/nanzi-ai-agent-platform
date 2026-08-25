from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_prompt_studio_specs_modal_contract():
    view = _source("frontend/src/views/PromptStudio.vue")

    # 1. 验证 ? 号按钮与状态定义
    assert "showSpecsModal" in view
    assert "activeSpecsTab" in view
    assert "提示词工坊设计规范与使用指南" in view

    # 2. 验证三大 Tab 核心技术概念
    assert "核心架构与测试流" in view or "Architecture" in view
    assert "动态变量与模板语法" in view or "Variables & Syntax" in view
    assert "版本管理与发布实践" in view or "Best Practice" in view
    assert "{schema_info}" in view
    assert "{few_shot_examples}" in view


def test_datasource_management_specs_modal_contract():
    view = _source("frontend/src/views/DataSourceManagement.vue")

    # 1. 验证 ? 号按钮与状态定义
    assert "showSpecsModal" in view
    assert "activeSpecsTab" in view
    assert "数据源管理设计规范与表画像摸排指南" in view

    # 2. 验证三大 Tab 核心技术概念
    assert "核心架构与表画像流程" in view or "Architecture & Profiling" in view
    assert "连接配置与安全隔离规范" in view or "Security & Connections" in view
    assert "故障排查与最佳实践" in view or "Best Practice" in view
    assert "只读账号" in view
