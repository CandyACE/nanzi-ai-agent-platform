"""API 工具「向导模式」契约（静态源码断言 + 跨层口径断言）。

钉住的都是**改坏了会静默出错**的地方：

1. 向导不得有自己的数据模型（出现 ``wizardForm`` 就是分叉的开始，终将「切 tab 丢内容」）；
2. 「重新解析」不得自动覆盖用户手改过的参数（静默丢数据，且用户无从察觉）；
3. 试跑前必须拦住未填的必填参数（不让带 ``{city}`` 的请求发出去）；
4. 试跑失败必须分清「接口拒绝了」与「根本没连上」——这两种给的建议完全不同；
5. 私网地址必须提示但**不阻止**（与运行时同权的既定决策）；
6. 后端试跑必须复用运行时请求内核，而不是另写一套（否则「试跑通过、运行时失败」）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

REGISTRY = Path("frontend/src/components/system/ToolRegistry.vue")
WIZARD = Path("frontend/src/components/system/ToolWizard.vue")
TESTER = Path("frontend/src/components/system/ApiToolTester.vue")
TOOLS_ENDPOINT = Path("app/api/portal/endpoints/tools.py")


def _source(path: Path) -> str:
    if not path.exists():
        pytest.fail(f"缺少文件：{path}")
    return path.read_text(encoding="utf-8")


def _body(source: str, marker: str) -> str:
    """取以 ``marker`` 开头那个块的括号平衡内容（函数体）。"""
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[brace : index + 1]
    raise AssertionError(f"未找到平衡块：{marker}")


# --------------------------------------------------------------------------- #
# 入口：两个 tab
# --------------------------------------------------------------------------- #
def test_registry_exposes_both_editor_modes():
    source = _source(REGISTRY)
    assert "editorMode" in source
    assert ">表单模式</button>" in source
    assert ">向导模式" in source


def test_registry_keeps_one_save_path():
    """向导与表单都必须落到同一个 saveTool，否则校验与提交时机又会分叉。"""
    source = _source(REGISTRY)
    assert source.count("const saveTool") == 1
    assert "@click=\"saveTool\"" in source


# --------------------------------------------------------------------------- #
# 向导：单一数据源 + 不自动覆盖
# --------------------------------------------------------------------------- #
def test_wizard_has_no_second_data_model():
    """红线：向导只能写父组件的 toolForm，不能自带一套字段。"""
    source = _source(WIZARD)
    assert "wizardForm" not in source, "向导不得引入第二个数据模型"
    assert "toolForm" in source


def test_wizard_has_four_steps():
    source = _source(WIZARD)
    for title in ("粘贴请求", "起名与描述", "确认参数", "试跑一次"):
        assert title in source, f"向导缺少步骤：{title}"
    # 参数由纯函数推导，不在组件里手写规则
    assert "buildDraftParams" in source


def test_reparse_never_overwrites_params_automatically():
    """改完地址后参数可能过期，但**只有用户点按钮**才允许覆盖。"""
    source = _source(WIZARD)
    assert '@click="regenerateParams"' in source, "缺少「重新生成参数」按钮"
    # 除了模板绑定，任何地方都不许调用它（解析流程里调用 = 静默覆盖手改内容）
    assert "regenerateParams()" not in source, "重新生成只能由按钮触发，不能在解析流程里自动调用"
    # 粘贴框变化只标记「可能已过期」
    assert "staleParams.value = true" in source
    assert "不会自动覆盖" in source


def test_wizard_uses_shared_param_editor():
    """向导与表单共用同一个参数编辑器——两份 UI 必然漂移。"""
    source = _source(WIZARD)
    assert "<ToolParamEditor" in source
    assert 'mode="wizard"' in source


def test_wizard_flags_non_get_as_really_sent():
    """平台把登记的工具当只读能力交给智能体，但请求是真的会发出去。"""
    source = _source(WIZARD)
    assert "请求会真实发出" in source


# --------------------------------------------------------------------------- #
# 试跑面板
# --------------------------------------------------------------------------- #
def test_tester_blocks_missing_required_params():
    source = _source(TESTER)
    assert "missingRequired" in source
    body = _body(source, "const runPreview")
    assert "missingRequired.value.length > 0" in body, "试跑前必须拦住未填的必填参数"


def test_tester_distinguishes_rejection_from_unreachable():
    """「接口拒绝」与「根本没连上」的排查方向完全不同，不能合并成一句「失败」。"""
    source = _source(TESTER)
    assert "地址是通的，但接口拒绝了这次请求" in source
    assert "根本没连上目标接口" in source


def test_tester_warns_about_private_targets_without_blocking():
    source = _source(TESTER)
    assert "isPrivateTarget" in source
    assert 'v-if="isPrivateTarget"' in source, "私网地址必须有醒目提示"
    # 但绝不能因为私网就不让试跑（与运行时同权）
    body = _body(source, "const runPreview")
    assert "isPrivateTarget" not in body, "私网判断不得成为试跑的拦截条件"


def test_tester_says_params_are_not_persisted():
    source = _source(TESTER)
    assert "测试值不会保存到工具配置里" in source


def test_tester_passes_draft_to_preview_api():
    source = _source(TESTER)
    assert "toolApi.preview" in source
    assert "url_template" in source
    assert "params" in source


# --------------------------------------------------------------------------- #
# 后端：试跑必须复用运行时内核（跨层口径）
# --------------------------------------------------------------------------- #
def test_preview_endpoint_reuses_runtime_request_kernel():
    """另写一套请求逻辑 = 「试跑能过、运行时调不通」，这是本特性最该防的事。"""
    source = _source(TOOLS_ENDPOINT)
    assert "GenericApiToolFactory._perform_request" in source
    # 非 2xx 要拿到原始响应才能分类展示，而不是让它抛异常
    assert "raise_on_http_error=False" in source


def test_preview_endpoint_requires_same_permission_as_writes():
    """试跑与创建/更新同权：既不放宽，也不额外收紧。"""
    source = _source(TOOLS_ENDPOINT)
    assert '@router.post("/preview"' in source
    preview = source[source.index('@router.post("/preview"'):]
    preview = preview[: preview.index("\n@router.") if "\n@router." in preview else len(preview)]
    assert "SYSTEM_CONFIG_SAVE_PERMISSION" in preview


# --------------------------------------------------------------------------- #
# 可用性：tab 对比度、步骤不折行、门禁、示例
# --------------------------------------------------------------------------- #
def test_tab_switch_has_a_visible_selected_state():
    """两个 tab 必须一眼看出选中哪个。

    原先选中态只有「白底 + 灰底容器」，未选中是 ``text-gray-400``——在浅灰底上两者
    几乎糊在一起，用户实测反馈「tab 切换不清晰」。
    """
    source = _source(REGISTRY)
    start = source.rindex("<", 0, source.index('aria-label="填写方式"'))
    group = source[start:]
    group = group[: group.index("</div>")]

    # 选中态：白底 + 蓝字 + 描边，而不是仅靠底色深浅
    assert "ring-1 ring-primary/40" in group
    assert "font-semibold text-primary" in group
    # 未选中态不能再是浅到看不清的 gray-400
    assert "text-gray-400" not in group, "未选中 tab 的对比度不足"
    # 无障碍：状态要能被读出来
    assert group.count(":aria-pressed=") == 2
    # 容器本身给一层浅色底与内描边，让白底选中块浮起来
    assert "bg-gray-200/70" in group and "ring-inset" in group


def test_wizard_steps_stay_on_a_single_row():
    """四个步骤必须一排放下（用户实测反馈：步骤条折行成 3+1）。"""
    source = _source(WIZARD)
    start = source.rindex("<", 0, source.index('aria-label="向导步骤"'))
    steps = source[start:]
    steps = steps[: steps.index("</ol>")]

    assert "grid-cols-4" in steps, "步骤条应等分四列"
    assert "flex-wrap" not in steps, "步骤条不得折行"
    # hint 文案始终展示（原先窄屏用 hidden 藏起来，等于把解释删了）
    assert 'class="hidden text-[11px]' not in steps


def test_modal_is_wide_enough_for_the_four_steps():
    """弹窗要跟着加宽，否则四步挤在一起又要折行。"""
    source = _source(REGISTRY)
    assert "max-w-5xl" in source
    assert "max-w-3xl" not in source


def test_wizard_blocks_forward_until_the_step_is_complete():
    """没解析成功 / 名字没填 / 必填参数没描述，就不许往下走。

    门禁必须同时做三件事，缺一件就会退化成「按钮灰着但不说为什么」：
    给出阻塞原因、限制可去步骤、把「下一步」绑上门禁。
    """
    source = _source(WIZARD)

    assert "stepBlockers" in source
    assert "maxStep" in source
    assert "canGoTo" in source
    assert "const goToStep" in source

    # 「下一步」不能再直接改 step，必须过门禁
    assert '@click="goToStep(step + 1)"' in source
    assert ':disabled="!canGoTo(step + 1)"' in source
    # 步骤条点击同样要过门禁
    assert "goToStep(item.id)" in source
    # 阻塞原因要显示出来
    assert "currentBlocker" in source
    assert "{{ currentBlocker }}" in source

    # 三条阻塞规则各自存在
    assert "blockers[1]" in source and "blockers[2]" in source and "blockers[3]" in source


def test_step_three_checks_the_live_schema_not_the_parse_snapshot():
    """第 3 步的「必填参数有描述吗」必须看编辑器里的实时内容。

    解析快照（``draftParams``）在用户于编辑器里补描述之后并不会更新，
    拿它做判断会出现「明明写了描述还是过不去」。
    """
    source = _source(WIZARD)
    # 必须直接解析「编辑器手里的那份 JSON」，而不是拿解析快照重建
    assert "parseToolSchema(props.toolForm.parameter_schema_str)" in source
    assert "paramsMissingDescription" in source
    # 快照仍用于展示「为什么这么判」，但门禁不能建立在它上面
    assert "liveSchema" in source


def test_wizard_offers_a_one_click_example_request():
    """第一次用的人不该被「粘贴什么」卡住——给一条真实形状的示例。"""
    source = _source(WIZARD)

    assert "EXAMPLE_CURL" in source
    assert "const insertExample" in source
    assert '@click="insertExample"' in source
    assert "插入示例" in source
    # 示例要覆盖三类参数，否则演示不出解析能力
    curl = source[source.index("const EXAMPLE_CURL"):]
    curl = curl[: curl.index("`\n") + 2] if "`\n" in curl else curl
    assert "-X POST" in curl
    assert "-H '" in curl
    assert "-d '" in curl
    assert "{order_id}" in curl


def test_inserting_the_example_does_not_falsely_mark_params_stale():
    """插入示例后不能立刻提示「参数可能已过期」。

    ``watch(pasteText)`` 是异步（pre-flush）执行的：``insertExample`` 同步把它赋值并
    解析成功后，watcher 才回头跑，此时 ``staleParams`` 会被错误地重新置为 true。
    所以要按「文本是否真的变过」判断，而不是「watch 是否触发过」。
    """
    source = _source(WIZARD)
    assert "parsedFromText" in source
    assert "value !== parsedFromText.value" in source
    # 解析成功时记录依据文本
    assert "parsedFromText.value = pasteText.value" in source
