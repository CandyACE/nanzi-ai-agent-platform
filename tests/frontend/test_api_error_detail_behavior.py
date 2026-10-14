"""接口错误详情的可读化（F4），纯函数行为测试。

问题：用户页把 `detail` 直接塞给 toast，FastAPI 422 的 detail 是
`[{loc, msg, type}, ...]`，于是界面上显示 `[object Object]`；角色页则只说
「保存权限失败」，管理员既不知道哪一项坏了，也不知道是不是自己的输入问题。

所以统一走一个纯函数：422 的数组按「字段 + 人话」拼成一句，字符串 detail 原样透传，
没有 detail 时退回 message / 兜底文案。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/apiErrorDetail.ts"
pytestmark = pytest.mark.no_infrastructure


def _run_typescript(expression: str):
    script = f"""
(async () => {{
const fs = require('fs');
const ts = require('./frontend/node_modules/typescript');
const source = fs.readFileSync({json.dumps(MODULE)}, 'utf8');
const code = ts.transpileModule(source, {{
  compilerOptions: {{ module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }}
}}).outputText;
const moduleRef = {{ exports: {{}} }};
new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, require);
const api = moduleRef.exports;
const result = await (async () => {{ {expression} }})();
process.stdout.write(JSON.stringify(result));
}})().catch(error => {{ console.error(error); process.exit(1); }});
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_fastapi_422_detail_array_becomes_a_readable_sentence():
    """Pydantic 的 string_too_long 要变成「禁用工具长度不能超过 255 个字符」这类人话。"""
    detail = [
        {
            "type": "string_too_long",
            "loc": ["body", "forbidden_tools", 0],
            "msg": "String should have at most 255 characters",
            "input": "x" * 300,
        }
    ]
    result = _run_typescript(
        f"return {{ text: api.extractApiErrorDetail({{ detail: {json.dumps(detail)} }}) }};"
    )

    assert result["text"] == "禁用工具长度不能超过 255 个字符"


def test_multiple_422_items_are_joined_and_capped():
    """多条错误用「；」连起来，只详细说前三条，其余收敛成计数，避免 toast 撑爆。"""
    detail = [
        {"type": "string_too_long", "loc": ["body", "forbidden_commands", 0], "msg": "String should have at most 255 characters"},
        {"type": "missing", "loc": ["body", "forbidden_skills"], "msg": "Field required"},
        {"type": "string_type", "loc": ["body", "models", 2], "msg": "Input should be a valid string"},
        {"type": "string_type", "loc": ["body", "agents", 3], "msg": "Input should be a valid string"},
    ]
    result = _run_typescript(
        f"return {{ text: api.extractApiErrorDetail({{ detail: {json.dumps(detail)} }}) }};"
    )

    text = result["text"]
    assert "禁用命令关键字长度不能超过 255 个字符" in text
    assert "禁用技能不能为空" in text
    assert "可用模型格式不正确" in text
    assert text.count("；") == 3, "三条详细 + 一条计数"
    assert "其余 1 项" in text


def test_string_and_message_details_pass_through():
    """字符串 detail 原样用；没有 detail 时退回 message；都没有才用兜底文案。"""
    result = _run_typescript(
        """
return {
  stringDetail: api.extractApiErrorDetail({ detail: '该邮箱已被其他账号使用' }),
  messageOnly: api.extractApiErrorDetail({ message: '用户名已存在' }),
  nothing: api.extractApiErrorDetail({}),
  nullPayload: api.extractApiErrorDetail(null),
  undefinedPayload: api.extractApiErrorDetail(undefined),
  customFallback: api.extractApiErrorDetail({}, '保存失败'),
};
"""
    )

    assert result["stringDetail"] == "该邮箱已被其他账号使用"
    assert result["messageOnly"] == "用户名已存在"
    assert result["nothing"] == "操作失败"
    assert result["nullPayload"] == "操作失败"
    assert result["undefinedPayload"] == "操作失败"
    assert result["customFallback"] == "保存失败"


def test_never_renders_object_object():
    """无论 detail 长什么样，都不能把对象 / 数组直接 stringify 成 `[object Object]`。"""
    result = _run_typescript(
        """
const payloads = [
  { detail: [{ loc: ['body'], type: 'unknown_thing' }] },
  { detail: [{ loc: [], msg: '' }] },
  { detail: [] },
  { detail: { loc: ['body'], msg: '嵌套对象' } },
  { detail: 42 },
  { message: 42 },
];
return payloads.map((payload) => api.extractApiErrorDetail(payload));
"""
    )

    for text in result:
        assert isinstance(text, str) and text.strip(), "必须总是给出非空文案"
        assert "[object Object]" not in text


def test_unknown_fields_still_produce_a_sentence_with_the_raw_field_name():
    """没登记中文标签的字段也不能丢信息：沿用原始字段名。"""
    detail = [
        {"type": "value_error", "loc": ["body", "quota_policy", "daily"], "msg": "value is not a valid integer"}
    ]
    result = _run_typescript(
        f"return {{ text: api.extractApiErrorDetail({{ detail: {json.dumps(detail)} }}) }};"
    )

    assert result["text"] == "daily：value is not a valid integer"
