"""智能体版本「是否允许手动切换模型」契约测试。

覆盖三件事：
1. 版本配置抽屉在「模型策略」步骤提供胶囊开关，历史数据默认开启；
2. 前端输入框在该开关关闭时隐藏模型切换入口；
3. 后端字段/服务/迁移与前端一致，且缺省值恒为「允许」。
"""

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]


def test_model_step_exposes_allow_switch_toggle_defaulting_to_on():
    source = (ROOT / "frontend/src/components/agent/AgentVersionEditorDrawer.vue").read_text(encoding="utf-8")
    # 只截取「模型策略」步骤模板区间，避免命中工具步骤里另一个 switch
    model_step = source[source.index("versionConfigStep === 'model'"):source.index("<!-- Step 2: Tools -->")]

    assert "allowModelSwitch" in model_step
    assert "允许在输入框手动切换模型" in model_step
    assert 'role="switch"' in model_step
    assert "默认开启" in model_step
    assert "历史版本未配置时同样按「允许切换」处理" in model_step
    assert "看不到模型切换入口" in model_step
    # 默认开启：只有显式 false 才算「禁止切换」
    assert "props.versionForm.allow_model_switch !== false" in source
    assert "allowModelSwitch = !allowModelSwitch" in model_step


def test_api_type_and_version_form_carry_allow_model_switch():
    agent_api = (ROOT / "frontend/src/api/agent.ts").read_text(encoding="utf-8")
    management = (ROOT / "frontend/src/views/AgentManagement.vue").read_text(encoding="utf-8")

    assert "allow_model_switch?: boolean" in agent_api
    assert "allow_model_switch?: boolean | null" in agent_api
    # 新建 / 引导 / 默认三种版本表单初始化都显式声明默认开启
    assert management.count("allow_model_switch: true") >= 3


def test_chat_input_hides_model_switcher_when_agent_forbids_switching():
    source = (ROOT / "frontend/src/components/embed/ChatInput.vue").read_text(encoding="utf-8")

    assert "allowModelSwitch?: boolean" in source
    assert "allowModelSwitch: true" in source
    dropdown = source[source.index("Custom Model Dropdown Selector"):]
    assert 'v-if="allowModelSwitch"' in dropdown[:400]


def test_embed_chat_passes_flag_and_ignores_model_override():
    source = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    # 可见性由 chatModelSwitch 统一裁决（版本开关 × 模型白名单候选，见模型白名单设计 §4.8）
    assert ':allow-model-switch="chatModelSwitch.visible"' in source
    assert "versionAllowsSwitch: manualModelSwitchAllowed.value" in source
    # 智能体查找收敛到 effectiveChatAgent，开关与「已发布版本模型名」共用同一次查找
    assert "effectiveChatAgent.value?.allow_model_switch !== false" in source
    # 禁用后不再下发输入框遗留的模型覆盖与模型参数覆盖
    assert "model: effectiveOverrideModel.value || undefined" in source
    assert "manualModelSwitchAllowed.value && thinkingEnableOverride.value !== null" in source
    assert "manualModelSwitchAllowed.value && temperatureOverride.value !== null" in source


def test_backend_defaults_to_on_and_propagates_version_flag():
    schema = (ROOT / "app/schemas/agent.py").read_text(encoding="utf-8")
    model = (ROOT / "app/models/agent.py").read_text(encoding="utf-8")
    service = (ROOT / "app/services/ai/agent_manager.py").read_text(encoding="utf-8")
    endpoints = (ROOT / "app/api/portal/endpoints/agents.py").read_text(encoding="utf-8")

    # 版本创建/更新/复制/运行时配置四条链路都要带字段，且方向一致
    assert "allow_model_switch: bool = True" in schema
    assert "allow_model_switch: Optional[bool] = None" in schema
    assert "allow_model_switch = Column(Boolean, nullable=False, default=True)" in model
    assert 'if "allow_model_switch" in data.model_fields_set:' in service
    assert service.count("allow_model_switch=bool(getattr(") >= 4
    # /agents/allowed 与 embed-access 需要附带「已发布版本」的开关
    assert "attach_published_model_switch_flags" in service
    assert "attach_published_model_switch_flags" in endpoints
