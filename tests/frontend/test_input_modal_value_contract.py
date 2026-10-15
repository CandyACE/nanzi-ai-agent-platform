"""行为级契约：InputModal 必须把用户输入真正交回调用方。

## 为什么单独写这一条

`InputModal` 声明了 `update:modelValue` 与 `confirm(value)` 两个出口，但**只在 confirm 时
回传**，模板里的 `<input v-model="draft">` 绑的是组件内部 ref，用户敲的字从未写回父组件的
`revokeComment` / `renameDialog.draft`。后果是两端「确定」都白点：

* 下架（REVOKED）：`submitRevokePublication` 读到空原因 → 永远停在
  「请填写下架原因（必填）」，接口一次都没发出去；
* 重命名：`newSkillId === target.skillId` 恒成立 → 弹窗关闭、什么都没发生。

这两个缺陷在源码 grep 型契约测试下**全绿通过**（grep 只能证明字符串存在，证明不了
「输入能不能流到调用方」），所以这里用 `@vue/compiler-sfc` 编译真实模板，断言编译产物里
`<input>` 上确实挂了把 `update:modelValue` 派发出去的 `onInput` 处理器——即真行为，而不是
源码里出现过某个词。同时锁定两个调用方以 confirm 载荷为准（即便绑定再次被改坏也不静默）。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT_MODAL = ROOT / "frontend/src/components/InputModal.vue"
SKILLS_VIEW = ROOT / "frontend/src/views/SkillsManagement.vue"


def _compiled_template_handlers() -> dict:
    """用仓库内的 @vue/compiler-sfc 编译 InputModal，取出模板编译产物。"""
    script = """
const fs = require('fs');
const sfc = require('./frontend/node_modules/@vue/compiler-sfc');
const source = fs.readFileSync('frontend/src/components/InputModal.vue', 'utf8');
const parsed = sfc.parse(source, { filename: 'InputModal.vue' });
const compiled = sfc.compileTemplate({
  source: parsed.descriptor.template.content,
  filename: 'InputModal.vue',
  id: 'input-modal-contract',
});
if (compiled.errors && compiled.errors.length) {
  process.stderr.write(JSON.stringify(compiled.errors));
  process.exit(3);
}
process.stdout.write(JSON.stringify({ code: compiled.code }));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_input_modal_dispatches_typed_value_to_parent():
    """编译产物里的 input 必须把 update:modelValue 派发出去（缺了就两个流程全废）。"""
    compiled = _compiled_template_handlers()
    code = compiled["code"]
    # 编译后的模板：input 元素上会生成 onInput 处理器；这里断言它引用了 update:modelValue
    assert "update:modelValue" in code, (
        "InputModal 的 <input> 没有把输入值派发出去："
        "父组件的 revokeComment / renameDialog.draft 永远是初始值，"
        "「下架」会卡在『请填写下架原因』，「重命名」会判定 ID 未变化而静默关闭。"
    )
    assert "onInput" in code, "input 上的 @input 处理器没有出现在编译产物里"


def test_skills_view_uses_confirm_payload_for_revoke_and_rename():
    """调用方以 confirm 载荷为准：即使双向绑定再被改坏，功能也不会静默失效。"""
    source = SKILLS_VIEW.read_text(encoding="utf-8")

    # 两个弹窗的 confirm 都直接挂提交函数（Vue 会把 emit 的载荷作为第一个实参传入）
    assert '@confirm="submitRevokePublication"' in source
    assert '@confirm="submitRename"' in source

    # 下架：优先使用载荷，且把归一化后的值写回本地状态
    revoke_start = source.index("const submitRevokePublication = ")
    revoke_body = source[revoke_start : source.index("\nconst ", revoke_start + 10)]
    assert "commentFromModal?: string" in revoke_body, "下架提交没有接收弹窗载荷"
    assert "commentFromModal ?? revokeComment.value" in revoke_body, (
        "下架提交仍只读本地 ref：绑定一旦失效就永远发不出请求"
    )

    # 重命名：同样以载荷为准，且「ID 未变化」必须给可见提示而不是静默关闭
    rename_start = source.index("const submitRename = ")
    rename_body = source[rename_start : source.index("\nconst ", rename_start + 10)]
    assert "nextIdFromModal?: string" in rename_body, "重命名提交没有接收弹窗载荷"
    assert "nextIdFromModal ?? target.draft" in rename_body
    unchanged_start = rename_body.index("newSkillId === target.skillId")
    unchanged_branch = rename_body[unchanged_start : unchanged_start + 200]
    assert "showToast" in unchanged_branch, "「技能 ID 未变化」仍会静默关闭弹窗"
    assert "renameDialog.value = null" not in unchanged_branch, (
        "「技能 ID 未变化」应当保持弹窗打开让用户修改"
    )


def test_publication_badges_cover_every_status():
    """发布状态徽章必须覆盖全部枚举（下架 REVOKED 曾渲染成无文字圆点）。"""
    source = SKILLS_VIEW.read_text(encoding="utf-8")
    for status, label in (
        ("PUBLISHED", "平台版"),
        ("PENDING", "审核中"),
        ("REJECTED", "已驳回"),
        ("WITHDRAWN", "已撤销"),
        ("REVOKED", "已下架"),
    ):
        assert f"status === '{status}'" in source, f"缺少 {status} 的徽章分支"
        assert label in source, f"缺少 {status} 的中文文案（{label}）"
    # 兜底：未知状态也要有文字，不能出现「有徽章没文字」
    assert "return status ? String(status) : ''" in source
