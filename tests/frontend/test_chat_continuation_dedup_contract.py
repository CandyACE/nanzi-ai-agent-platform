from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def test_continuation_actions_have_function_level_submission_guards():
    for relative_path in (
        "frontend/src/views/EmbedChat.vue",
        "frontend/src/views/AgentDebug.vue",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        for function_name, marker in (
            ("submitPendingExternalExecution", "pendingExternalExecution"),
            ("confirmPendingPermission", "pendingPermission"),
        ):
            start = source.index(f"const {function_name} = async")
            body = source[start:]
            assert "pending.isSubmitting" in body, (relative_path, function_name)
            assert "|| pending.isSubmitting" in body, (relative_path, function_name)
            assert body.index("pending.isSubmitting") < body.index("await "), (relative_path, function_name)
            assert marker in body

