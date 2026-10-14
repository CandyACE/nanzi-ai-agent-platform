"""Contract tests for personal skills experience (center + chat mount scope)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PERSONAL_CENTER = ROOT / "frontend" / "src" / "views" / "PersonalCenter.vue"
SKILLS_MGMT = ROOT / "frontend" / "src" / "views" / "SkillsManagement.vue"
EMBED = ROOT / "frontend" / "src" / "views" / "EmbedChat.vue"
DEBUG = ROOT / "frontend" / "src" / "views" / "AgentDebug.vue"
CASCADE = ROOT / "frontend" / "src" / "components" / "embed" / "SkillCascadeMenu.vue"
CHAT_INPUT = ROOT / "frontend" / "src" / "components" / "embed" / "ChatInput.vue"
BANNER = ROOT / "frontend" / "src" / "components" / "chat" / "SkillCreatedBanner.vue"
SKILL_CREATED_UTIL = ROOT / "frontend" / "src" / "utils" / "skillCreated.ts"
EXEC_TOOLS = ROOT / "app" / "services" / "ai" / "tools" / "system_executive_tools.py"


def test_personal_center_exposes_skills_tab():
    text = PERSONAL_CENTER.read_text(encoding="utf-8")
    assert "'skills'" in text or '"skills"' in text
    assert "personal-only" in text or "personalOnly" in text
    assert "SkillsManagement" in text
    assert "skill_id" in text


def test_skills_management_supports_personal_only_mode():
    text = SKILLS_MGMT.read_text(encoding="utf-8")
    assert "personalOnly" in text
    assert "initialSkillId" in text
    assert "v-if=\"!personalOnly\"" in text


def test_skills_workbench_prioritizes_enabled_skills_before_disabled():
    text = SKILLS_MGMT.read_text(encoding="utf-8")
    sorted_section = text[text.index("const getSkillStatusRank"):text.index("const toggleSkillSortOrder")]

    # 判定走统一的 isSkillEnabled（与后端 skill_metadata.is_skill_enabled 同口径），
    # 不再就地比较字符串：手写 enabled: False/0/off 时旧写法会把它排在「已启用」前面。
    assert "!isSkillEnabled(skill.enabled) ? 1 : 0" in sorted_section
    assert "const statusOrder = getSkillStatusRank(a) - getSkillStatusRank(b)" in sorted_section
    assert "if (statusOrder !== 0) return statusOrder" in sorted_section
    assert "skillSortBy.value === 'time'" in sorted_section
    assert "aKey.localeCompare(bKey, 'zh-CN') * dir" in sorted_section


def test_chat_mount_includes_skill_scope():
    for path in (EMBED, DEBUG, CHAT_INPUT):
        text = path.read_text(encoding="utf-8")
        assert "scope," in text or "scope:" in text
        assert 'scope === "personal"' in text or "scope === 'personal'" in text
    for path in (EMBED, DEBUG):
        text = path.read_text(encoding="utf-8")
        assert "SkillCreatedBanner" in text


def test_skill_cascade_empty_state_points_to_personal_center():
    text = CASCADE.read_text(encoding="utf-8")
    assert "/dashboard/personal?tab=skills" in text
    assert "SkillCascadeMenu" in CHAT_INPUT.read_text(encoding="utf-8") or "skill-cascade" in CHAT_INPUT.read_text(encoding="utf-8").lower()
    assert "SkillCascadeMenu" in CHAT_INPUT.read_text(encoding="utf-8")
    assert "min(28rem" in text
    assert "fillHeight" in text
    assert "flex-1 min-h-0" in text
    assert "left-full top-0 bottom-0" in CHAT_INPUT.read_text(encoding="utf-8")


def test_create_skills_emits_machine_marker():
    text = EXEC_TOOLS.read_text(encoding="utf-8")
    assert "NANZI_SKILL_CREATED" in text
    assert BANNER.exists()
    assert "parseSkillCreatedMarker" in SKILL_CREATED_UTIL.read_text(encoding="utf-8")


def test_create_skills_requires_explicit_overwrite():
    """``create_skills`` 不得静默覆盖同名技能。

    回归背景：原先 ``makedirs(exist_ok=True)`` 后直接整份覆盖已存在的 SKILL.md，
    却无条件返回 ``NANZI_SKILL_CREATED``、前端弹「已创建个人技能」横幅——用户以为
    新增了一个技能，实际把已有技能（可能已发布、已被智能体挂载）的正文清空替换。
    现在：默认拒写并返回 ``NANZI_SKILL_EXISTS``，只有显式 ``overwrite=true`` 才覆盖，
    且覆盖走 ``NANZI_SKILL_UPDATED`` 标记以便前端换文案。
    """
    text = EXEC_TOOLS.read_text(encoding="utf-8")
    assert "overwrite: bool = False" in text
    assert "NANZI_SKILL_EXISTS" in text
    assert "NANZI_SKILL_UPDATED" in text
    assert "already_exists = os.path.exists(skill_md_path)" in text
    # 默认分支必须直接 return，不能落到写盘逻辑
    assert "if already_exists and not overwrite:" in text


def test_skill_created_banner_deduplicates_and_uses_latest_marker():
    """「已创建个人技能」横幅必须去重并取最新标记。

    回归背景：视图侧 watch 扫描的是**整个会话历史**，而 ``NANZI_SKILL_CREATED``
    标记会随工具输出长期保留；原先既没有按 ``skill_id`` 去重，又用正则取「第一个」
    匹配，于是每次 messages 变化（发消息 / 流式回复 / 刷新加载历史 / 切回会话）都会
    重新弹出横幅，点 ✕ 关闭后下一轮又出现，且创建过多个技能时永远显示最早那一个。
    """
    util = SKILL_CREATED_UTIL.read_text(encoding="utf-8")
    # 取「最后一个」标记，而不是第一个匹配
    assert "export function parseLatestSkillCreatedMarker" in util
    assert "MARKER_RE_GLOBAL" in util
    # 按 skill_id 去重，并按会话持久化（刷新页面不再重复打扰）
    assert "export function createSkillNotifyGate" in util
    assert "localStorage" in util
    # 保留原有的首个匹配解析（其它调用方与既有契约）
    assert "export function parseSkillCreatedMarker" in util
    # 覆盖更新必须与新建区分文案，且去重键包含 action
    assert "NANZI_SKILL_(CREATED|UPDATED)" in util
    assert "export type SkillCreatedAction" in util
    assert "function notifyKey(" in util

    for path in (EMBED, DEBUG):
        text = path.read_text(encoding="utf-8")
        assert "createSkillNotifyGate(() => conversationId.value)" in text
        assert "parseLatestSkillCreatedMarker(blob)" in text
        # action 参与去重键：创建与「覆盖更新」是两件事，都要各提示一次
        assert "skillNotifyGate.shouldNotify(info.skill_id, info.action)" in text
        assert "skillNotifyGate.mark(skillCreatedInfo.value.skill_id, skillCreatedInfo.value.action)" in text
        assert "const dismissCreatedSkill = ()" in text
        assert "skillNotifyGate.mark(" in text
        # 关闭必须记入已提示，不能只把状态置空
        assert '@dismiss="dismissCreatedSkill"' in text
        assert '@dismiss="skillCreatedInfo = null"' not in text
        # 不应再拿「首个匹配」直接赋值弹出
        assert "parseSkillCreatedMarker(blob)" not in text
