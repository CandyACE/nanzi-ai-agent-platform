"""契约：平台技能「下架」（撤销已发布版本）的前端闭环。

后端接口契约（已冻结，对接方不得自行改形）：

    GET  /api/portal/skills/publications
         → {"status": "success", "data": {"items": [{publication_id, version_id, skill_id,
            platform_skill_id, name, description, publication_status: "PUBLISHED",
            version_number, source_user_id, submitted_by, published_at, reviewed_by,
            file_count, total_size}]}}
    POST /api/portal/skills/publications/{version_id}/revoke
         body {"comment": "..."}（必填非空）
         → 成功后前端刷新列表；422（原因为空）/404（记录不存在）/409（已下架或不是当前版本）
           都必须把后端原因显示出来。

回归背景：发布通道是「一次性」的——管理员点了「通过并发布」之后，平台技能库里就有了
对全员可见的版本，而工作台没有任何回收入口；发布错了、或事后发现技能包里有风险脚本，
只能去改数据库。这次补上「已发布 / 下架管理」分区，并且明确三点产品约束：

  1. 入口与列表沿用现有表格样式与 `element:skills:admin` 权限口径（个人技能页不可达）；
  2. 下架是线上操作，必须先确认影响面、再强制填写下架原因，空原因不得提交；
  3. 失败不得静默——后端给出的原因必须变成用户可见的报错提示。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS_VIEW = ROOT / "frontend" / "src" / "views" / "SkillsManagement.vue"

pytestmark = pytest.mark.no_infrastructure


def _source() -> str:
    return SKILLS_VIEW.read_text(encoding="utf-8")


def _function_body(name: str, end_marker: str) -> str:
    """截取 `const <name> = ...` 到下一个已知锚点之间的源码，用于按函数断言。"""
    source = _source()
    start = source.index(f"const {name} = ")
    end = source.index(end_marker, start)
    return source[start:end]


def test_published_list_uses_frozen_endpoint_and_permission_scope():
    source = _source()
    # 列表接口与冻结契约一致
    assert "axios.get('/api/portal/skills/publications')" in source
    assert "response.data.data?.items || []" in source
    # 入口挂在平台技能管理视图上：仍用现有权限口径，个人技能页不可达
    assert 'id="tab-skill-publications"' in source
    assert 'v-if="canManagePlatformSkills"' in source
    assert "已发布" in source
    assert "已发布 / 下架管理" in source
    assert 'activeWorkspaceTab === \'publications\' && canAccessPlatformWorkspace' in source
    # 分区与「待审核」并列，且不依赖 tab bar 之外的隐式状态
    assert "id=\"tab-skill-publication-review\"" in source
    assert source.index('id="tab-skill-publication-review"') < source.index('id="tab-skill-publications"')


def test_revoke_posts_required_comment_to_frozen_path():
    body = _function_body("submitRevokePublication", "const openPublicationReviewDetail")
    assert "/api/portal/skills/publications/${target.version_id}/revoke" in body
    # body 必须带 comment（后端 422 校验非空）
    assert "{ comment }" in body
    # 成功后刷新列表，避免已下架的记录还留在界面上可再次点击；
    # 平台技能清单也一并刷新（版本下线后清单会变）
    assert "fetchPublications()" in body
    assert "fetchSkills()" in body


def test_revoke_requires_confirmation_and_non_empty_reason():
    confirm_body = _function_body("startRevokePublication", "/**\n * 第二步")
    # 第一步必须是确认弹窗（复用 ConfirmModal 的 confirmState 机制）
    assert "confirmState.value = {" in confirm_body
    assert "title: '下架已发布技能'" in confirm_body
    assert "revokeTarget.value = item" in confirm_body

    submit_body = _function_body("submitRevokePublication", "const openPublicationReviewDetail")
    # 第二步强制填写原因：空原因就地提示且**不关闭**弹窗（保持打开才能补填）
    # 必须以 InputModal 回传的载荷为准：只读本地 ref 曾经让这里永远读到空字符串，
    # 于是「下架」100% 卡在提示上、接口一次都没发出去（InputModal 那时不派发输入值）。
    assert "commentFromModal ?? revokeComment.value" in submit_body
    assert 'commentFromModal?: string' in submit_body
    assert '@confirm="submitRevokePublication"' in _source(), (
        "confirm 载荷没接到提交函数上，收不到用户输入的原因"
    )
    assert "请填写下架原因（必填）" in submit_body
    empty_check = submit_body.index("if (!comment) {")
    request_index = submit_body.index("axios.post(`/api/portal/skills/publications/")
    assert empty_check < request_index, "空原因必须在发请求之前拦下"
    assert "revokeTarget.value = null" not in submit_body[:empty_check]

    source = _source()
    # 原因输入弹窗复用既有 InputModal（与重命名同款，含 loading 与必填提示）
    assert 'v-if="revokeTarget"' in source
    assert 'confirm-text="确认下架"' in source
    assert ":maxlength=\"REVOKE_COMMENT_MAX\"" in source
    assert 'placeholder="请填写下架原因（必填）"' in source


def test_revoke_failures_are_visible_with_backend_reason():
    body = _function_body("submitRevokePublication", "const openPublicationReviewDetail")
    # 422 / 404 / 409 等都靠后端 detail 呈现，不得静默或只 console
    assert "showToast(e.response?.data?.detail || '下架技能失败', 'error')" in body
    assert "console.warn" not in body and "console.error" not in body
    # 契约注释锁定三类错误码，避免以后有人「顺手」把 detail 吞掉
    assert "422（原因为空）" in body
    assert "404（记录不存在）" in body
    assert "409（已下架或不是当前版本）" in body


def test_revoke_success_feedback_and_list_refresh():
    body = _function_body("submitRevokePublication", "const openPublicationReviewDetail")
    assert "已下架「${target.name || target.skill_id}」v${target.version_number ?? '—'}" in body
    assert "'success'" in body
    # 提交期间置 loading，弹窗按钮转「处理中…」，避免重复下架
    assert "revokeSubmitting.value = true" in body
    assert "revokeSubmitting.value = false" in body


def test_revoke_reports_reference_cleanup_warnings():
    """下架会让公共技能目录真的消失，白名单/会话挂载引用清理失败必须如实告知。

    后端 `POST /publications/{version_id}/revoke` 返回体里带 `synced` / `warnings`
    （与重命名、删除同一风格）——静默丢弃就等于「技能没了但智能体还挂着断链」。
    """
    body = _function_body("submitRevokePublication", "const openPublicationReviewDetail")
    assert "const { syncedCount, warnings } = summarizeReferenceSync(response.data?.data)" in body
    assert "已同步 ${syncedCount} 处引用" in body
    assert "有 ${warnings.length} 条警告" in body
    assert "warnings.join('；')" in body
    assert "warnings.length ? 'error' : 'success'" in body
    # 信封不是 success 时不能再报「已下架」
    assert "showToast(response.data?.message || '下架技能失败', 'error')" in body
    assert body.index("if (response.data?.status !== 'success')") < body.index("已下架「")


def test_revoke_view_reuses_existing_table_style_and_shows_contract_fields():
    source = _source()
    # 与技能列表视图同款表格样式，不另造一套视觉
    table_class = 'class="min-w-full divide-y divide-gray-200 text-left"'
    assert source.count(table_class) >= 2
    # 契约字段都要能显示出来
    for field in ("item.version_number", "item.platform_skill_id", "item.file_count", "item.published_at"):
        assert field in source
    assert "const formatPublishedAt" in source
    # 已发布记录的 published_at 是 ISO 字符串，不能当秒级时间戳渲染
    assert "if (Number.isNaN(date.getTime())) return String(value)" in source


def test_published_view_is_not_reachable_from_personal_only_page():
    source = _source()
    open_body = _function_body("openPublications", "/**\n * 第一步")
    # 打开分区前先过 canAccessPlatformWorkspace（personalOnly 或无 element:skills:admin 时拒绝）
    assert "if (!canAccessPlatformWorkspace.value)" in open_body
    assert open_body.index("canAccessPlatformWorkspace.value") < open_body.index("activeWorkspaceTab.value = 'publications'")
    assert "仅平台技能管理员可用" in open_body


def test_publications_prefetch_is_silent_and_click_does_not_leak_event():
    source = _source()
    assert "const fetchPublications = async (silent = false) => {" in source
    # 首屏静默预取（只为让 tab 数量角标准确），失败不打扰尚未进入该分区的用户
    assert "fetchPublications(true)" in source
    body = _function_body("fetchPublications", "/** 打开「已发布 / 下架管理」分区")
    assert body.count("if (!silent) {") == 2
    # 「刷新」按钮必须显式调用，不能把 MouseEvent 当 silent 传进去（事件对象是 truthy，
    # 会把手动刷新也变成静默失败）
    assert '@click="fetchPublications()"' in source
    assert '@click="fetchPublications"' not in source


def test_badge_shows_pending_new_version_while_online_version_stays_published():
    """★ 已发布 + 又提交了一版待审时，徽章必须告诉作者"线上仍是旧版、新版在审"。

    后端为这种谱系保持 ``publication_status=PUBLISHED``（否则管理员就下架不掉正在线上服务
    的那一版），只有 ``pending_version`` 这个字段能表达"还有新版本在审"。若徽章只显示
    「平台版 vN」，作者会以为自己刚提交的内容已经生效，管理员也看不出还有待审版本。
    """
    body = _function_body("publicationBadgeLabel", "\nconst publicationBadgeClass")
    assert "skill.pending_version" in body, "徽章必须读取 pending_version"
    assert "新版审核中" in body
    # 仍要保留线上版本号
    assert "current_public_version" in body


def test_reference_sync_counts_agent_id_lists():
    """★ `synced.agents` 是智能体 ID 列表，不是条数：必须按长度累加。

    `Number(['a','b'])` 是 NaN → 此前被当成 0，于是真的同步了智能体白名单之后，
    提示语反而显示"已同步 0 处引用"，用户以为什么都没改。
    """
    body = _function_body("summarizeReferenceSync", "\n/** 打开重命名弹窗")
    assert "Array.isArray(value)" in body, "列表类要按长度计数"
    assert "value.length" in body
