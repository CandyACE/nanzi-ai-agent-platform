"""Contract: 任务约束指令字段、帮助引导与列表标识。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK_CENTER = ROOT / "frontend" / "src" / "views" / "TaskCenter.vue"
TASK_API = ROOT / "frontend" / "src" / "api" / "task.ts"


def test_task_center_exposes_constraints_field_and_help_entry():
    text = TASK_CENTER.read_text(encoding="utf-8")

    assert "任务约束指令" in text
    assert "taskConstraints" in text
    assert "showConstraintsHelpModal" in text
    assert 'title="查看填写说明与示例"' in text
    assert 'maxlength="2000"' in text


def test_task_center_explains_purpose_and_priority():
    text = TASK_CENTER.read_text(encoding="utf-8")

    assert "任务约束指令填写说明" in text
    assert "执行指令决定" in text
    assert "以这里为准" in text
    for token in ("输出形态", "业务口径", "数据范围", "禁止事项"):
        assert token in text
    assert "留空即不生效" in text
    assert "需要强制生效的格式要求，请写在这里" in text


def test_task_center_provides_fillable_examples():
    text = TASK_CENTER.read_text(encoding="utf-8")

    assert "constraintExamples" in text
    assert "applyConstraintExample" in text
    for title in ("移动端列表交付", "统一口径与单位", "限定数据范围", "精简交付"):
        assert title in text


def test_task_center_persists_constraints_in_config():
    text = TASK_CENTER.read_text(encoding="utf-8")

    assert "baseConfig.task_constraints" in text
    assert "delete baseConfig.task_constraints" in text
    assert "cfg.task_constraints" in text


def test_task_center_marks_tasks_with_constraints():
    text = TASK_CENTER.read_text(encoding="utf-8")

    assert "task.config?.task_constraints" in text
    assert "该任务已配置任务约束指令" in text


def test_task_api_config_type_declares_constraints():
    text = TASK_API.read_text(encoding="utf-8")

    assert "task_constraints?: string" in text
