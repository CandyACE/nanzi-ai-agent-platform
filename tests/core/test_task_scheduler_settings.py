import pytest

from app.core.config import Settings


pytestmark = pytest.mark.no_infrastructure


def _build_settings(**overrides):
    values = {
        "_env_file": None,
        "REDIS_HOST": "localhost",
        "ENCRYPTION_KEY": "KkJgK_d-1Jda9CAp7iGhRDzuXLYZfnid2siBeIC5lqw=",
    }
    values.update(overrides)
    return Settings(**values)


def test_task_scheduler_is_enabled_by_default():
    assert _build_settings().TASK_SCHEDULER_ENABLED is True


def test_task_scheduler_can_be_disabled_per_node():
    assert _build_settings(TASK_SCHEDULER_ENABLED=False).TASK_SCHEDULER_ENABLED is False
