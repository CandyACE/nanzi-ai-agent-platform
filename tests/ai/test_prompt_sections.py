import pytest

from app.services.ai.prompt_sections import PromptSection, render_prompt_sections


pytestmark = pytest.mark.no_infrastructure


def test_prompt_sections_render_in_stable_order_and_skip_disabled_or_empty_blocks():
    rendered = render_prompt_sections(
        [
            PromptSection("late", 20, "Late"),
            PromptSection("empty", 10, "  "),
            PromptSection("disabled", 5, "Disabled", enabled=False),
            PromptSection("early", 10, " Early "),
        ]
    )

    assert rendered == "Early\n\nLate"
