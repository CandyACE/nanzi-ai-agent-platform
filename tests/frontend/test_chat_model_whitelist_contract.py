"""前端接线契约：聊天作用域 API、权限弹窗「可用模型」资源页、未配置=不限制文案。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_API = (ROOT / "frontend/src/api/model.ts").read_text(encoding="utf-8")
ROLES = (ROOT / "frontend/src/views/Roles.vue").read_text(encoding="utf-8")
USERS = (ROOT / "frontend/src/views/Users.vue").read_text(encoding="utf-8")


def test_model_api_exposes_chat_scoped_listing():
    assert "listAvailableForChat" in MODEL_API
    assert "scope: 'chat'" in MODEL_API
    # 管理端语义不能被改动
    assert "list: (type?: string, includeInactive = false)" in MODEL_API


def test_permission_dialogs_have_model_whitelist_page():
    for source in (ROLES, USERS):
        assert "models: []" in source
        assert "可用模型" in source
        assert "未配置 = 不限制" in source


def test_saving_permissions_sends_models_array():
    for source in (ROLES, USERS):
        assert "models:" in source


def test_embed_chat_uses_chat_scoped_candidates_only():
    """候选只来自白名单（scope=chat），且不再把智能体默认模型单列成候选项。

    下拉第一项固定是「使用默认模型」（不覆盖 = 跟随智能体/平台默认），单列一份是重复的，
    因此接线里不应再出现 published_model_name / agentDefaultModel / isAgentDefault。
    """
    source = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    assert "resolveChatModelSwitch" in source
    assert "listAvailableForChat" in source
    assert "published_model_name" not in source
    assert "agentDefaultModel" not in source
    assert "isAgentDefault" not in source


def test_permission_model_page_supports_search():
    """模型太多：资源页要能按名称/ID 过滤，且复用输入框那套阈值。"""
    for source in (ROLES, USERS):
        assert "groupPermissionModels" in source
        assert "modelSearchQuery" in source
        assert "shouldShowModelSearch" in source
        assert "搜索模型" in source


def test_permission_model_page_groups_selected_first():
    """已勾选项不能被淹没：默认视图就分「已选」与「其余」两段带标题渲染。"""
    for source in (ROLES, USERS):
        assert "已选 " in source
        assert "其余 " in source
        # 分组必须在 models 页生效，其它资源页仍走平铺列表
        assert "modelResourceGroups" in source


def test_chat_rejection_copy_is_wired_on_both_sides():
    """后端 detail 与前端 403 判定共用同一文案子串——改文案会同时红，不会静默失效。"""
    chat = (ROOT / "app/api/v1/endpoints/chat.py").read_text(encoding="utf-8")
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    assert "该模型不在你的可用范围内" in chat
    assert 'errorMessage.includes("可用范围")' in embed


def test_switch_visibility_no_longer_depends_on_agent_selection():
    """候选里不再有默认模型项后，「是否指定智能体」的阈值分支已无意义，不应留在纯函数调用里。"""
    source = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    assert "hasAgent" not in source
