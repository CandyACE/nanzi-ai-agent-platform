from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_message_renderer_marks_only_supported_script_languages_as_runnable():
    source = _source("frontend/src/components/MessageRenderer.vue")

    assert "RUNNABLE_CODE_LANGUAGES" in source
    assert "python3" in source
    assert "shell" in source
    assert "runnable: RUNNABLE_CODE_LANGUAGES.has(lang)" in source
    assert "langName: lang" in source


def test_chat_canvas_has_confirmed_inline_execution_with_live_output_and_stop():
    source = _source("frontend/src/components/embed/ChatCanvas.vue")
    composable = _source("frontend/src/composables/chat/useCodeExecution.ts")

    assert "useCodeExecution" in source
    assert "确认运行" in source
    assert "取消" in source
    assert "停止运行" in source
    assert "stdout" in source
    assert "stderr" in source
    assert "data.runnable" in source
    assert "/api/v1/chat/code-executions/stream" in composable
    assert "/api/v1/chat/code-executions/" in composable
    assert "conversation_id" in composable


def test_code_execution_composable_parses_sse_and_exposes_running_state():
    source = _source("frontend/src/composables/chat/useCodeExecution.ts")

    for token in (
        "getReader()",
        "event:",
        "data:",
        "executionId",
        "isRunning",
        "outputChunks",
        "stopExecution",
    ):
        assert token in source


def test_workspace_source_files_keep_script_execution_metadata():
    canvas = _source("frontend/src/components/embed/ChatCanvas.vue")
    preview = _source("frontend/src/utils/workspaceFilePreview.ts")

    assert "props.data.runnable === true" in canvas
    assert "resolveWorkspaceScriptLanguage" in preview
    assert "runnable: !!scriptLanguage" in preview
    assert "sourcePath?: string" in canvas


def test_code_execution_uses_code_and_output_tabs_instead_of_vertical_split():
    source = _source("frontend/src/components/embed/ChatCanvas.vue")

    assert "codeExecutionTab" in source
    assert "代码" in source
    assert "运行输出" in source
    assert "@click=\"codeExecutionTab = 'code'\"" in source
    assert "@click=\"codeExecutionTab = 'output'\"" in source
    assert "codeExecutionTab === 'output'" in source


def test_run_output_exposes_copy_and_ai_analysis_floaters():
    source = _source("frontend/src/components/embed/ChatCanvas.vue")

    assert "outputCopied" in source
    assert "copyCodeOutput" in source
    assert "发送到 AI 分析" in source
    assert "analyze-output" in source
    assert "codeOutputText" in source
    assert "hasCodeOutput" in source


def test_output_analysis_is_prefilled_into_existing_chat_input():
    embed = _source("frontend/src/views/EmbedChat.vue")
    debug = _source("frontend/src/views/AgentDebug.vue")

    for source in (embed, debug):
        assert "@analyze-output=\"handleAnalyzeCodeOutput\"" in source
        assert "handleAnalyzeCodeOutput" in source
        assert "userInput.value = question" in source
        assert "chatInputRef.value?.focus()" in source


def test_workspace_canvas_preserves_script_metadata_when_normalizing_payload():
    source = _source("frontend/src/composables/chat/useWorkspaceCanvas.ts")

    assert "langName?: string" in source
    assert "runnable?: boolean" in source
    assert "langName: payload.langName" in source
    assert "runnable: payload.runnable" in source
