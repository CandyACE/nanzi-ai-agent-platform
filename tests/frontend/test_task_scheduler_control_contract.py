from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]


def test_scheduler_start_is_gated_by_node_environment_setting():
    config = (ROOT / "app/core/config.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    env_example = (ROOT / "env.example").read_text(encoding="utf-8")
    compose = (ROOT / "docker/docker-compose.yml").read_text(encoding="utf-8")
    k8s_config = (ROOT / "k8s_deploy/configmap.yaml").read_text(encoding="utf-8")

    assert "TASK_SCHEDULER_ENABLED: bool = True" in config
    assert "if settings.TASK_SCHEDULER_ENABLED:" in main
    assert "TASK_SCHEDULER_ENABLED 已关闭" in main
    assert "TASK_SCHEDULER_ENABLED=true" in env_example
    assert "TASK_SCHEDULER_ENABLED=${TASK_SCHEDULER_ENABLED:-true}" in compose
    assert 'TASK_SCHEDULER_ENABLED: "true"' in k8s_config


def test_task_center_exposes_smart_agent_retry_configuration():
    page = (ROOT / "frontend/src/views/TaskCenter.vue").read_text(encoding="utf-8")

    for marker in (
        "taskMaxRetries",
        "taskRetryDelayMinutes",
        "max_retries",
        "retry_delay_seconds",
        "执行失败策略",
        "最大重试次数",
        "重试间隔",
        "立即执行不自动重试",
    ):
        assert marker in page
