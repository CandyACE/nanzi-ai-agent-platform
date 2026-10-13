"""公共技能「已禁用」的三处挂载入口接线契约。

产品口径：**看得见、但置灰不可选，并写明原因**——不从列表里移除（移除会让用户以为技能丢了）。
判定口径必须单一：三处入口（外加渲染 EmbedChat 技能网格的子组件）都调
`frontend/src/utils/skillForbidden.ts`，不允许各自内联 `skill.forbidden`，
否则迟早出现「一处按布尔判、一处按真值判」的漂移。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SKILL_CENTER = ROOT / "frontend/src/components/embed/SkillCascadeMenu.vue"
EMBED_CHAT = ROOT / "frontend/src/views/EmbedChat.vue"
RESOURCE_MODAL = ROOT / "frontend/src/components/embed/ResourceScopeModal.vue"
TASK_COMPOSER = ROOT / "frontend/src/components/task/TaskPromptComposer.vue"
# 反向断言用：管理员侧不受禁用限制，这两页必须保持零改动
AGENT_MANAGEMENT = ROOT / "frontend/src/views/AgentManagement.vue"
SKILLS_MANAGEMENT = ROOT / "frontend/src/views/SkillsManagement.vue"

UTILS = (ROOT / "frontend/src/utils/skillForbidden.ts").read_text(encoding="utf-8")

# EmbedChat 只负责把接口数据带下去，技能网格实际渲染在 ResourceScopeModal 里，
# 所以「入口 + 渲染」共 4 个文件，全部走同一份判定。
CONSUMERS = (SKILL_CENTER, EMBED_CHAT, RESOURCE_MODAL, TASK_COMPOSER)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _body(source: str, header: str) -> str:
    """截取某个函数 / 计算属性的函数体，用下一个顶格 `}` 收尾。"""
    assert header in source, f"未找到锚点：{header}"
    lines: list[str] = []
    for line in source.split(header, 1)[1].splitlines():
        if line.startswith("}") or line.startswith(");"):
            break
        lines.append(line)
    assert lines, f"锚点 {header} 之后没有函数体"
    return "\n".join(lines)


def test_judgement_lives_in_one_place_and_every_entry_point_uses_it():
    """纯函数是唯一判定来源；四个文件都 import 并调用它，且不得内联字段比较。"""
    assert "export function isSkillForbidden(" in UTILS
    assert "export function forbiddenSkillReason(" in UTILS
    assert "export const FORBIDDEN_SKILL_BADGE = '已禁用'" in UTILS
    assert "skill?.forbidden === true" in UTILS, "必须严格判等，缺字段 / 字符串一律按未禁用"

    for path in CONSUMERS:
        source = _source(path)
        assert "@/utils/skillForbidden" in source, f"{path.name} 必须复用同一份判定"
        assert "isSkillForbidden(" in source, f"{path.name} 必须调用判定函数"
        assert "forbidden ===" not in source, f"{path.name} 不得各自内联判断 forbidden 字段"


def test_skill_center_shows_forbidden_skills_but_blocks_mounting():
    """会话输入框技能中心：置灰 + 不可点 + 红色「已禁用」标签 + title 说明原因。"""
    source = _source(SKILL_CENTER)

    assert "forbidden?: boolean" in source, "SkillItem 必须声明后端新增字段"
    assert ':disabled="attachedIdSet.has(skill.id) || isSkillForbidden(skill)"' in source
    assert "opacity-60 cursor-not-allowed" in source, "禁用态要置灰"
    assert "{{ FORBIDDEN_SKILL_BADGE }}" in source
    assert "bg-red-50" in source and "text-red-600" in source, "禁用标签用红色系，与「已挂载」的灰区分"
    assert ':title="isSkillForbidden(skill) ? forbiddenSkillReason(skill) : undefined"' in source

    # 优先级：已挂载 > 已禁用。两者都必须不可点，但既挂载又被禁时显示「已挂载」（灰），
    # 禁用标签走 v-else-if 分支，保证不会同时冒出两个标签自相矛盾。
    assert 'v-else-if="isSkillForbidden(skill)"' in source
    assert source.index(">已挂载</span>") < source.index('v-else-if="isSkillForbidden(skill)"')


def test_skill_center_mount_path_has_its_own_guard():
    """不能只靠 :disabled——点击 / 回车 / 父级直接调用都可能进 mountSkill。"""
    body = _body(_source(SKILL_CENTER), "const mountSkill = (skill: SkillItem) => {")

    assert "isSkillForbidden(skill)" in body
    assert "return" in body
    assert body.index("isSkillForbidden(skill)") < body.index("emit('select'"), "守卫必须在 emit 之前"
    assert "该技能已挂载，请勿重复挂载" in body, "已挂载的原有提示不变"


def test_forbidden_skills_stay_visible_in_the_skill_center_list():
    """被禁技能不进搜索/过滤的排除逻辑：仍然看得见，只是点不动。"""
    body = _body(_source(SKILL_CENTER), "const filteredSkillsList = computed(() => {")
    assert "forbidden" not in body.lower(), "列表过滤不得因禁用剔除技能"


def test_embed_chat_carries_the_flag_through_and_guards_the_toggle():
    """EmbedChat：技能选项带上 forbidden（个人技能缺字段 → false），并在写入草稿前拦一道。"""
    source = _source(EMBED_CHAT)

    assert "forbidden: isSkillForbidden(item)" in source, "接口字段要先归一成布尔再往下传"
    body = _body(
        source,
        "const toggleModalResourceOption = (type: ResourceScopeGroupKey, option: any) => {",
    )
    assert "isSkillForbidden(option)" in body
    assert "type === 'skills'" in body
    assert "!selected" in body, "只拦「选中」方向：禁用前保存过的历史项还要能取消"
    assert body.index("isSkillForbidden(option)") < body.index(
        "resourceScopeModalDraft.value ="
    ), "守卫必须在写入草稿之前"


def test_resource_scope_modal_grays_out_forbidden_skills():
    """会话固定资源弹窗的技能网格：置灰、不可勾选、带原因；历史已选项允许取消。"""
    source = _source(RESOURCE_MODAL)

    assert "isSkillOptionLocked(option)" in source
    assert "isSkillForbidden(option)" in source
    assert "bg-red-50" in source and "text-red-600" in source
    assert "{{ FORBIDDEN_SKILL_BADGE }}" in source
    assert "forbiddenSkillReason(option, '勾选')" in source
    assert "cursor-not-allowed" in source

    body = _body(source, "const skillsForActiveScope = computed(() => {")
    assert "forbidden" not in body.lower(), "技能列表仍按 平台/个人 + 搜索词过滤，不排除被禁项"


def test_task_prompt_composer_grays_out_forbidden_skills():
    """任务提示词编辑器的技能面板：同样置灰、不可勾选、带原因，且提交方向有守卫。"""
    source = _source(TASK_COMPOSER)

    assert "forbidden?: boolean" in source, "TaskScopeItem 必须声明后端新增字段"
    assert "forbidden: isSkillForbidden(item)" in source
    assert "isSkillOptionLocked(item)" in source
    assert "bg-red-50" in source and "text-red-600" in source
    assert "{{ FORBIDDEN_SKILL_BADGE }}" in source
    assert "forbiddenSkillReason(item, '勾选')" in source
    assert "cursor-not-allowed" in source

    toggle = _body(source, "const toggleScopeItem = (")
    assert "isSkillForbidden(item)" in toggle
    assert "return" in toggle
    assert toggle.index("isSkillForbidden(item)") < toggle.index("current.push(item)"), (
        "守卫必须在 push 之前"
    )

    scope = _body(source, "const skillsForActiveScope = computed(() => {")
    assert "forbidden" not in scope.lower(), "技能列表不得因禁用被过滤掉"


def test_admin_views_are_out_of_scope():
    """反向断言：管理员不受禁用限制，配智能体绑定技能 / 技能管理页必须零改动。"""
    for path in (AGENT_MANAGEMENT, SKILLS_MANAGEMENT):
        source = _source(path)
        assert "forbidden" not in source.lower(), f"{path.name} 不该出现禁用态处理"
        assert "FORBIDDEN_SKILL_BADGE" not in source, f"{path.name} 不该出现用户侧禁用文案"
