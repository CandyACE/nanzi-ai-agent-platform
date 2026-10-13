"""模型下拉的过滤/搜索纯函数行为契约。

模型列表动辄几十条，搜索必须「按名称与 ID 都能命中、空查询返回全部且不改动入参」，
这些行为用仓库既有的 node transpile harness 直接跑 `frontend/src/utils/modelSelect.ts`。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure

MODULE = "frontend/src/utils/modelSelect.ts"


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


MODELS_JS = """
const models = [
  { model_id: "deepseek-v3-2", name: "DeepSeek-V3.2", type: "llm", is_active: true },
  { model_id: "qwen-vl-max", name: "Qwen-VL-Max", type: "multimodal", is_active: true },
  { model_id: "legacy-embed", name: "Legacy Embedding", type: "embedding", is_active: true },
  { model_id: "retired-llm", name: "Retired LLM", type: "llm", is_active: false },
];
"""


def test_selectable_models_keep_only_active_llm_and_multimodal():
    assert _run_typescript(
        MODELS_JS + """
return api.selectableLlmModels(models).map(m => m.model_id);
"""
    ) == ["deepseek-v3-2", "qwen-vl-max"]


def test_selectable_models_tolerates_empty_input():
    assert _run_typescript(
        """
return [
  api.selectableLlmModels(null).length,
  api.selectableLlmModels(undefined).length,
];
"""
    ) == [0, 0]


def test_filter_returns_everything_for_blank_query_and_does_not_mutate_input():
    assert _run_typescript(
        MODELS_JS + """
const copy = api.filterSelectableModels(models, "   ");
const before = models.length;
api.filterSelectableModels(models, "").push({ model_id: "injected", type: "llm" });
return { ids: copy.map(m => m.model_id), unchanged: models.length === before };
"""
    ) == {
        "ids": ["deepseek-v3-2", "qwen-vl-max", "legacy-embed", "retired-llm"],
        "unchanged": True,
    }


def test_filter_matches_name_or_model_id_case_insensitively():
    assert _run_typescript(
        MODELS_JS + """
return {
  byName: api.filterSelectableModels(models, "v3.2").map(m => m.model_id),
  byNameUpper: api.filterSelectableModels(models, "QWEN").map(m => m.model_id),
  byId: api.filterSelectableModels(models, "VL-MAX").map(m => m.model_id),
  trimmed: api.filterSelectableModels(models, "  deepseek  ").map(m => m.model_id),
  missed: api.filterSelectableModels(models, "gpt-5").map(m => m.model_id),
};
"""
    ) == {
        "byName": ["deepseek-v3-2"],
        "byNameUpper": ["qwen-vl-max"],
        "byId": ["qwen-vl-max"],
        "trimmed": ["deepseek-v3-2"],
        "missed": [],
    }


def test_search_box_only_appears_for_long_lists():
    assert _run_typescript(
        """
return {
  threshold: api.MODEL_SEARCH_THRESHOLD,
  small: api.shouldShowModelSearch(api.MODEL_SEARCH_THRESHOLD - 1),
  atThreshold: api.shouldShowModelSearch(api.MODEL_SEARCH_THRESHOLD),
  big: api.shouldShowModelSearch(48),
};
"""
    ) == {"threshold": 6, "small": False, "atThreshold": True, "big": True}


def test_option_label_prefixes_multimodal_and_optional_model_id():
    assert _run_typescript(
        """
const llm = { model_id: "deepseek-v3-2", name: "DeepSeek-V3.2", type: "llm" };
const vl = { model_id: "qwen-vl-max", name: "Qwen-VL-Max", type: "multimodal" };
const unnamed = { model_id: "mystery-model", name: "", type: "llm" };
return {
  plain: api.modelOptionLabel(llm),
  multimodal: api.modelOptionLabel(vl),
  withId: api.modelOptionLabel(vl, { showModelId: true }),
  fallbackToId: api.modelOptionLabel(unnamed),
};
"""
    ) == {
        "plain": "DeepSeek-V3.2",
        "multimodal": "🖼️ Qwen-VL-Max",
        "withId": "🖼️ Qwen-VL-Max (qwen-vl-max)",
        "fallbackToId": "mystery-model",
    }


def test_trigger_label_prefers_model_name_and_falls_back_to_id():
    assert _run_typescript(
        MODELS_JS + """
return {
  selected: api.resolveModelSelectionLabel(models, "deepseek-v3-2"),
  selectedMultimodal: api.resolveModelSelectionLabel(models, "qwen-vl-max"),
  withId: api.resolveModelSelectionLabel(models, "qwen-vl-max", { showModelId: true }),
  unknownId: api.resolveModelSelectionLabel(models, "removed-model"),
};
"""
    ) == {
        "selected": "DeepSeek-V3.2",
        "selectedMultimodal": "🖼️ Qwen-VL-Max",
        "withId": "🖼️ Qwen-VL-Max (qwen-vl-max)",
        "unknownId": "removed-model",
    }


def test_trigger_label_distinguishes_placeholder_from_empty_option():
    assert _run_typescript(
        MODELS_JS + """
return {
  orchestratorPlaceholder: api.resolveModelSelectionLabel(models, "", { placeholder: "选择编排模型..." }),
  followOrchestrator: api.resolveModelSelectionLabel(models, "", { allowEmpty: true, emptyLabel: "跟随编排模型" }),
  toolDefault: api.resolveModelSelectionLabel(models, "", { allowEmpty: true }),
  fallbackWithoutModels: api.resolveModelSelectionLabel(null, "legacy-model"),
};
"""
    ) == {
        "orchestratorPlaceholder": "选择编排模型...",
        "followOrchestrator": "跟随编排模型",
        "toolDefault": "跟随智能体默认配置",
        "fallbackWithoutModels": "legacy-model",
    }


def test_multimodal_type_helper_covers_all_registered_type_names():
    """各供应商登记多模态的方式不一，vision / image2text 也要算多模态。"""
    assert _run_typescript(
        """
return {
  types: api.MULTIMODAL_MODEL_TYPES,
  multimodal: api.isMultimodalModelType("multimodal"),
  visionUpper: api.isMultimodalModelType("VISION"),
  image2text: api.isMultimodalModelType("image2text"),
  llm: api.isMultimodalModelType("llm"),
  missing: api.isMultimodalModelType(undefined),
};
"""
    ) == {
        "types": ["multimodal", "vision", "image2text"],
        "multimodal": True,
        "visionUpper": True,
        "image2text": True,
        "llm": False,
        "missing": False,
    }


def test_build_model_options_prefixes_and_badges_multimodal_models():
    assert _run_typescript(
        """
const models = [
  { model_id: "deepseek-v3-2", name: "DeepSeek-V3.2", type: "llm" },
  { model_id: "qwen-vl-max", name: "Qwen-VL-Max", type: "vision" },
];
return {
  plain: api.buildModelOptions(models).map(o => o.label),
  withId: api.buildModelOptions(models, { showModelId: true }).map(o => o.label),
  badges: api.buildModelOptions(models, { showModelId: true, multimodalBadge: "· 多模态" }).map(o => o.label),
  values: api.buildModelOptions(models).map(o => o.value),
  emptyInput: api.buildModelOptions(null).length,
};
"""
    ) == {
        "plain": ["DeepSeek-V3.2", "🖼️ Qwen-VL-Max"],
        "withId": ["DeepSeek-V3.2 (deepseek-v3-2)", "🖼️ Qwen-VL-Max (qwen-vl-max)"],
        "badges": ["DeepSeek-V3.2 (deepseek-v3-2)", "🖼️ Qwen-VL-Max (qwen-vl-max) · 多模态"],
        "values": ["deepseek-v3-2", "qwen-vl-max"],
        "emptyInput": 0,
    }


def test_pinned_options_keep_unknown_current_value_and_empty_option():
    """列表外的当前值（环境变量注入 / 已停用）必须能看见还能选回去，否则换组件后配置会「消失」。"""
    assert _run_typescript(
        """
const models = [{ model_id: "deepseek-v3-2", name: "DeepSeek-V3.2", type: "llm" }];
return {
  unknownKept: api.buildPinnedModelOptions(models, "env-injected-model", { unknownOptionLabel: "未知/环境变量" }),
  knownNotPinned: api.buildPinnedModelOptions(models, "deepseek-v3-2", { unknownOptionLabel: "未知/环境变量" }),
  unknownWithoutLabel: api.buildPinnedModelOptions(models, "env-injected-model", {}),
  emptyOption: api.buildPinnedModelOptions(models, "", { allowEmpty: true, emptyLabel: "未配置（不支持识图时提示用户）" }),
  emptySkippedWhenNotAllowed: api.buildPinnedModelOptions(models, "", {}),
  bothPinned: api.buildPinnedModelOptions(models, "ghost-model", {
    allowEmpty: true, emptyLabel: "跟随编排模型", unknownOptionLabel: "未知/未启用",
  }).map(o => o.value),
};
"""
    ) == {
        "unknownKept": [{"value": "env-injected-model", "label": "env-injected-model (未知/环境变量)"}],
        "knownNotPinned": [],
        "unknownWithoutLabel": [],
        "emptyOption": [{"value": "", "label": "未配置（不支持识图时提示用户）"}],
        "emptySkippedWhenNotAllowed": [],
        "bothPinned": ["ghost-model", ""],
    }


def test_trigger_label_marks_unknown_value_when_label_provided():
    assert _run_typescript(
        MODELS_JS + """
return {
  withLabel: api.resolveModelSelectionLabel(models, "env-injected-model", { unknownOptionLabel: "未知/环境变量" }),
  withoutLabel: api.resolveModelSelectionLabel(models, "env-injected-model"),
};
"""
    ) == {
        "withLabel": "env-injected-model (未知/环境变量)",
        "withoutLabel": "env-injected-model",
    }
