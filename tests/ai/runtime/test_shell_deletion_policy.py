"""Shell 删除护栏的误报与真实删除行为回归测试。"""

import pytest

from app.services.ai.runtime.shell_deletion_policy import assess_shell_deletion


pytestmark = pytest.mark.no_infrastructure


WEATHER_HEREDOC_COMMAND = """curl -s https://www.weather.com.cn/weather/101010100.shtml | python3 - <<'PY'
# Find weather description
value = 1 if True else 2
print(value)
PY"""


def test_python_heredoc_weather_command_does_not_trigger_deletion_confirmation(tmp_path):
    decision = assess_shell_deletion(WEATHER_HEREDOC_COMMAND, cwd=tmp_path)

    assert decision.action == "pass"


def test_python_delete_call_still_requires_confirmation(tmp_path):
    command = """python3 - <<'PY'
import os
os.remove('report.txt')
PY"""

    decision = assess_shell_deletion(command, cwd=tmp_path)

    assert decision.action == "ask"


def test_python_subprocess_delete_of_protected_root_remains_denied(tmp_path):
    command = """python3 - <<'PY'
import subprocess
subprocess.run(['rm', '-rf', '/'])
PY"""

    decision = assess_shell_deletion(command, cwd=tmp_path)

    assert decision.action == "deny"


def test_shell_delete_of_protected_root_remains_denied(tmp_path):
    decision = assess_shell_deletion("rm -rf /", cwd=tmp_path)

    assert decision.action == "deny"
