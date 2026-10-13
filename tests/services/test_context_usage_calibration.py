"""输入框浮标的「实测校准」（P2）。

浮标原先只显示估算（`estimate_text_tokens` 的字节÷4 口径），实测低估约 21%
（明细弹框自报「估算 97k · 实际输入 123k」）。校准数据来自 middleware 写入的调用记录：
同一条 record 里既有真实 `input_tokens`，也有当次的 `context_breakdown.total_tokens`。

校准只作用于**对话消息**部分（system / tools 本就是 AgentScope 的真实计数），
且必须留在展示层——`session_status` 工具与运行时裁剪判定继续用纯估算（默认 calibrate=False）。
"""

import pytest

pytestmark = pytest.mark.no_infrastructure

# 用户实测样本：明细弹框 #24 的「估算 97k · 实际输入 123k」
SAMPLE = {
    "system_prompt_tokens": 12000,
    "tools_tokens": 11000,
    "estimated_total_tokens": 97000,
    "actual_input_tokens": 123498,
}
# 样本里对话部分的 ratio = (123498-23000) / (97000-23000) = 100498 / 74000 ≈ 1.3581
SAMPLE_RATIO = 100498 / 74000

WINDOW = 262144
HISTORY_BUDGET = 253952


async def _estimate(
    monkeypatch,
    *,
    sample,
    calibrate=None,
    history_bytes=4000,
    runtime_model_info=None,
):
    from app.services.ai import context_usage as cu

    async def fake_history(_user_id, _conversation_id):
        return [{"role": "user", "content": "x" * history_bytes}]

    async def fake_sample(**_kwargs):
        return sample

    async def fake_config_get(key, default=None):
        return str(WINDOW) if key == "agent_context_max_tokens" else default

    monkeypatch.setattr(cu.memory_service, "get_effective_context_history", fake_history)
    monkeypatch.setattr(cu, "_latest_runtime_context_sample", fake_sample)
    monkeypatch.setattr(cu.ConfigService, "get", fake_config_get)

    kwargs = {
        "user_id": "user-1",
        "conversation_id": "conversation-1",
        "runtime_model_info": runtime_model_info
        if runtime_model_info is not None
        else {
            "physical_window": WINDOW,
            "history_budget": HISTORY_BUDGET,
            "completion_reserve_tokens": 8192,
            "request_input_budget": WINDOW - 8192,
        },
        "empty_history_is_zero": True,
    }
    if calibrate is not None:
        kwargs["calibrate"] = calibrate
    return await cu.estimate_context_usage(**kwargs)


async def test_default_is_still_a_pure_estimate(monkeypatch):
    """不传 calibrate（session_status / 裁剪判定的用法）时语义必须完全不变。"""
    result = await _estimate(monkeypatch, sample=SAMPLE)

    assert result["estimated_current_tokens"] == 24000  # system 12000 + tools 11000 + history 1000
    assert result["current_tokens"] == 24000
    assert result["calibration"] == {
        "applied": False,
        "ratio": None,
        "sample_estimated_tokens": None,
        "sample_actual_tokens": None,
    }


async def test_calibrate_scales_only_the_conversation_part(monkeypatch):
    result = await _estimate(monkeypatch, sample=SAMPLE, calibrate=True)

    # 当前对话部分估算 1000 → 1000 × 1.3581 ≈ 1358；system/tools 保持不变
    assert result["estimated_current_tokens"] == 24000
    assert result["current_tokens"] == 23000 + round(1000 * SAMPLE_RATIO)
    assert result["calibration"]["applied"] is True
    assert result["calibration"]["ratio"] == pytest.approx(SAMPLE_RATIO)
    assert result["calibration"]["sample_estimated_tokens"] == 97000
    assert result["calibration"]["sample_actual_tokens"] == 123498


async def test_calibrated_breakdown_stays_self_consistent(monkeypatch):
    """面板「构成三项之和 = 顶部数字」不能被校准破坏。"""
    result = await _estimate(monkeypatch, sample=SAMPLE, calibrate=True)
    breakdown = result["context_breakdown"]

    assert breakdown["system_prompt_tokens"] == 12000
    assert breakdown["tools_tokens"] == 11000
    assert breakdown["conversation_tokens"] == round(1000 * SAMPLE_RATIO)
    assert breakdown["total_tokens"] == result["current_tokens"]
    assert (
        breakdown["system_prompt_tokens"]
        + breakdown["tools_tokens"]
        + breakdown["conversation_tokens"]
        == breakdown["total_tokens"]
    )


async def test_percentage_follows_the_calibrated_value(monkeypatch):
    calibrated = await _estimate(monkeypatch, sample=SAMPLE, calibrate=True)
    pure = await _estimate(monkeypatch, sample=SAMPLE, calibrate=False)

    assert calibrated["usage_percentage"] == round(
        calibrated["current_tokens"] / HISTORY_BUDGET * 100, 1
    )
    assert pure["usage_percentage"] == round(
        pure["estimated_current_tokens"] / HISTORY_BUDGET * 100, 1
    )
    assert calibrated["usage_percentage"] > pure["usage_percentage"]
    assert calibrated["estimated_remaining_tokens"] == HISTORY_BUDGET - calibrated["current_tokens"]


async def test_missing_sample_falls_back_to_estimate(monkeypatch):
    """没有可用的运行时样本时（新会话 / 记录缺失），展示值就等于纯估算。"""
    result = await _estimate(monkeypatch, sample=None, calibrate=True)

    # 无样本 ⇒ 没有 system/tools 开销可合并，估算只剩历史本身
    assert result["estimated_current_tokens"] == 1000
    assert result["current_tokens"] == result["estimated_current_tokens"]
    assert result["calibration"]["applied"] is False


async def test_low_ratio_sample_is_ignored(monkeypatch):
    """实测明显低于估算（ratio < 0.5）说明样本异常，不采信。"""
    tiny = {**SAMPLE, "actual_input_tokens": 23000 + 20000}  # ratio ≈ 0.27

    result = await _estimate(monkeypatch, sample=tiny, calibrate=True)

    assert result["calibration"]["applied"] is False
    assert result["current_tokens"] == 24000


async def test_high_ratio_sample_is_ignored(monkeypatch):
    huge = {**SAMPLE, "actual_input_tokens": 23000 + 74000 * 10}  # ratio = 10

    result = await _estimate(monkeypatch, sample=huge, calibrate=True)

    assert result["calibration"]["applied"] is False
    assert result["current_tokens"] == 24000


async def test_sample_with_too_small_conversation_part_is_ignored(monkeypatch):
    """样本对话部分太小（< 1000）时比值噪声大，不采信。"""
    small = {
        "system_prompt_tokens": 12000,
        "tools_tokens": 11000,
        "estimated_total_tokens": 23000 + 500,
        "actual_input_tokens": 23000 + 900,
    }

    result = await _estimate(monkeypatch, sample=small, calibrate=True)

    assert result["calibration"]["applied"] is False
    assert result["current_tokens"] == 24000


async def test_sample_without_actual_usage_is_ignored(monkeypatch):
    """旧记录可能没有真实 usage（usage_source 不可用），此时不能校准。"""
    result = await _estimate(
        monkeypatch,
        sample={**SAMPLE, "actual_input_tokens": 0},
        calibrate=True,
    )

    assert result["calibration"]["applied"] is False


async def test_calibration_keeps_budget_fields_untouched(monkeypatch):
    """校准只影响占用展示，模型窗口/预算字段必须原样透传。"""
    result = await _estimate(monkeypatch, sample=SAMPLE, calibrate=True)

    assert result["physical_window"] == WINDOW
    assert result["history_budget"] == HISTORY_BUDGET
    assert result["request_input_budget"] == WINDOW - 8192
    assert result["completion_reserve_tokens"] == 8192
