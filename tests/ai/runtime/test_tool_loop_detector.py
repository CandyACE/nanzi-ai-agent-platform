import pytest

from app.services.ai.runtime.tool_loop_detector import ToolLoopDetector

pytestmark = pytest.mark.no_infrastructure


def test_tool_loop_detector_fuses_on_repeated_identical_calls():
    detector = ToolLoopDetector(threshold=3, enabled=True)
    args = {"query": "hello world"}

    assert detector.record("search", args).fused is False
    assert detector.record("search", args).fused is False
    verdict = detector.record("search", args)
    assert verdict.fused is True
    assert verdict.count == 3
    assert "search" in verdict.message


def test_tool_loop_detector_normalizes_whitespace_and_key_order():
    detector = ToolLoopDetector(threshold=2, enabled=True)
    first = {"b": 1, "a": "  foo   bar  "}
    second = {"a": "foo bar", "b": 1}

    assert detector.record("tool", first).fused is False
    verdict = detector.record("tool", second)
    assert verdict.fused is True


def test_tool_loop_detector_fuses_on_repeated_get_current_time_regardless_of_args():
    detector = ToolLoopDetector(threshold=3, enabled=True)
    first = detector.record("get_current_time", {"timezone": "Asia/Shanghai"})
    second = detector.record("get_current_time", {"timezone": "UTC"})
    assert first.fused is False
    assert second.fused is True
    assert "get_current_time" in second.message


def test_tool_loop_detector_disabled_never_fuses():
    detector = ToolLoopDetector(threshold=1, enabled=False)
    for _ in range(5):
        assert detector.record("tool", {"x": 1}).fused is False


def test_ping_pong_fuses_on_alternating_tools():
    # threshold 高，避免同参重复先触发；ping_pong_threshold=4
    detector = ToolLoopDetector(threshold=99, ping_pong_threshold=4, global_limit=0)
    # 每次参数都不同，确保不是同参重复触发
    assert detector.record("get_schema", {"n": 1}).fused is False
    assert detector.record("run_sql", {"n": 2}).fused is False
    assert detector.record("get_schema", {"n": 3}).fused is False
    verdict = detector.record("run_sql", {"n": 4})
    assert verdict.fused is True
    assert verdict.reason_code == "ping_pong"
    assert "get_schema" in verdict.message and "run_sql" in verdict.message


def test_ping_pong_not_triggered_by_pure_repeat():
    # 同名工具连续调用属于 repeat，不应被误判为 ping_pong
    detector = ToolLoopDetector(threshold=99, ping_pong_threshold=3, global_limit=0)
    for i in range(5):
        verdict = detector.record("same_tool", {"n": i})
        assert verdict.reason_code != "ping_pong"
        assert verdict.fused is False


def test_global_circuit_breaker_fuses_on_total_calls():
    detector = ToolLoopDetector(threshold=99, ping_pong_threshold=0, global_limit=5)
    last = None
    for i in range(5):
        last = detector.record(f"tool_{i}", {"n": i})
    assert last.fused is True
    assert last.reason_code == "circuit_breaker"
    assert last.count == 5


def test_repeat_takes_precedence_over_other_detectors():
    detector = ToolLoopDetector(threshold=2, ping_pong_threshold=2, global_limit=2)
    args = {"q": "x"}
    assert detector.record("t", args).fused is False
    verdict = detector.record("t", args)
    assert verdict.fused is True
    assert verdict.reason_code == "repeat"


def test_fused_detector_stays_fused():
    detector = ToolLoopDetector(threshold=2, global_limit=0, ping_pong_threshold=0)
    args = {"q": "x"}
    detector.record("unrelated", {"q": "y"})
    detector.record("t", args)
    initial = detector.record("t", args)
    assert initial.fused is True
    assert initial.count == 2
    follow = detector.record("t", args)
    assert follow.fused is True
    assert follow.reason_code == initial.reason_code == "repeat"
    assert follow.message == initial.message
    assert follow.count == initial.count == 2
    assert detector.total_calls == 3
    assert detector.fused is True


def test_browser_action_resets_observation_repeat_counter():
    """测试多步表单操作中，每步调用 snapshot 不会被误判为同参 repeat 熔断。"""
    detector = ToolLoopDetector(threshold=3, ping_pong_threshold=6, global_limit=30)
    # 模拟 5 步正常自动化操作：open -> snap -> fill -> snap -> click -> snap -> fill -> snap -> click -> snap
    assert detector.record("browser_open", {"url": "https://example.com"}).fused is False
    assert detector.record("browser_snapshot", {}).fused is False
    assert detector.record("browser_fill", {"ref": "username", "value": "admin"}).fused is False
    assert detector.record("browser_snapshot", {}).fused is False
    assert detector.record("browser_click", {"ref": "next_btn"}).fused is False
    assert detector.record("browser_snapshot", {}).fused is False
    assert detector.record("browser_fill", {"ref": "pwd", "value": "123456"}).fused is False
    assert detector.record("browser_snapshot", {}).fused is False
    assert detector.record("browser_click", {"ref": "submit_btn"}).fused is False
    assert detector.record("browser_snapshot", {}).fused is False
    assert detector.fused is False


def test_browser_consecutive_snapshot_still_fuses():
    """测试连续纯调用 snapshot（无动作穿插）达到阈值时依然能正确熔断。"""
    detector = ToolLoopDetector(threshold=3, global_limit=30)
    assert detector.record("browser_snapshot", {}).fused is False
    assert detector.record("browser_snapshot", {}).fused is False
    verdict = detector.record("browser_snapshot", {})
    assert verdict.fused is True
    assert verdict.reason_code == "repeat"
    assert "browser_snapshot" in verdict.message


def test_browser_action_observation_cycle_exempt_from_ping_pong():
    """测试 Action ↔ Snapshot 交替循环不会被误判为 ping-pong 拉锯战。"""
    detector = ToolLoopDetector(threshold=99, ping_pong_threshold=4, global_limit=0)
    # fill ↔ snapshot 交替 6 次
    assert detector.record("browser_fill", {"ref": "f1", "value": "v1"}).fused is False
    assert detector.record("browser_snapshot", {}).fused is False
    assert detector.record("browser_fill", {"ref": "f2", "value": "v2"}).fused is False
    assert detector.record("browser_snapshot", {}).fused is False
    assert detector.record("browser_fill", {"ref": "f3", "value": "v3"}).fused is False
    verdict = detector.record("browser_snapshot", {})
    assert verdict.fused is False
    assert verdict.reason_code != "ping_pong"


def test_default_threshold_is_five():
    """测试默认 threshold=5，同参调用第 5 次触发熔断。"""
    detector = ToolLoopDetector(enabled=True)
    args = {"query": "SELECT * FROM users"}
    for _ in range(4):
        assert detector.record("execute_sql_query", args).fused is False
    verdict = detector.record("execute_sql_query", args)
    assert verdict.fused is True
    assert verdict.count == 5
    assert verdict.reason_code == "repeat"


def test_workspace_write_resets_read_file_repeat_counter():
    """测试多轮修改代码并读文件自测，不会被误判为同参 repeat 熔断。"""
    detector = ToolLoopDetector(threshold=3, ping_pong_threshold=6, global_limit=30)
    # 模拟“读 -> 改 -> 读 -> 改 -> 读 -> 改 -> 读”完整开发迭代
    assert detector.record("read_file", {"file_path": "main.py"}).fused is False
    assert detector.record("write_file", {"file_path": "main.py", "content": "v1"}).fused is False
    assert detector.record("read_file", {"file_path": "main.py"}).fused is False
    assert detector.record("write_file", {"file_path": "main.py", "content": "v2"}).fused is False
    assert detector.record("read_file", {"file_path": "main.py"}).fused is False
    assert detector.record("exec_command", {"command": "pytest"}).fused is False
    assert detector.record("read_file", {"file_path": "main.py"}).fused is False
    assert detector.fused is False


def test_workspace_action_observation_cycle_exempt_from_ping_pong():
    """测试 write_file ↔ read_file 代码开发交替循环不会被误判为 ping-pong 拉锯战。"""
    detector = ToolLoopDetector(threshold=99, ping_pong_threshold=4, global_limit=0)
    assert detector.record("write_file", {"file_path": "a.py", "content": "1"}).fused is False
    assert detector.record("read_file", {"file_path": "a.py"}).fused is False
    assert detector.record("write_file", {"file_path": "a.py", "content": "2"}).fused is False
    assert detector.record("read_file", {"file_path": "a.py"}).fused is False
    assert detector.record("write_file", {"file_path": "a.py", "content": "3"}).fused is False
    verdict = detector.record("read_file", {"file_path": "a.py"})
    assert verdict.fused is False
    assert verdict.reason_code != "ping_pong"


