"""接线契约：装配步骤必须把 user_info 中的约束传给提示词组装层。

该接线的错误方式（漏传）不会让任何单元测试失败——只会静默地让约束不生效，
因此以源码契约测试锁死。
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
ASSEMBLE_STEP = ROOT / "app" / "services" / "ai" / "pipeline" / "steps" / "assemble_step.py"
SCHEDULER = ROOT / "app" / "services" / "ai" / "scheduler_service.py"


def test_assemble_step_passes_task_constraints_from_user_info():
    text = ASSEMBLE_STEP.read_text(encoding="utf-8")
    assert 'user_info.get("task_constraints")' in text
    assert "task_constraints=task_constraints" in text


def test_scheduler_writes_task_constraints_into_user_info():
    text = SCHEDULER.read_text(encoding="utf-8")
    assert "_task_constraints_from_config(task_config)" in text
    assert 'user_info["task_constraints"] = task_constraints' in text


def test_scheduler_does_not_put_constraints_into_user_message():
    """约束必须走 system；user 消息（_build_scheduled_task_prompt）不得包含它。"""
    text = SCHEDULER.read_text(encoding="utf-8")
    body = text.split("def _build_scheduled_task_prompt(")[1]
    prompt_builder = re.split(r"\n(?:async )?def ", body)[0]
    assert "task_constraints" not in prompt_builder
