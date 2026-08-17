import pytest

from app.services.ai.runners.chatbi.repair_controller import ChatBIRepairController
from app.services.ai.runners.chatbi.constants import DATA_REPAIR_BUDGETS
from app.services.ai.runners.chatbi.run_state import DataRunState


pytestmark = pytest.mark.no_infrastructure


def test_controller_packages_schema_repair_and_applies_state_transition():
    state = DataRunState(
        requires_fresh_data=True,
        requires_sql_query=True,
        sql_before_schema=True,
    )
    controller = ChatBIRepairController(state)

    decision = controller.decide()

    assert decision is not None
    assert decision.kind == "sql_before_schema"
    assert decision.tool_choice.mode == "get_dataset_schema"
    assert decision.attempt == 0

    controller.begin(decision)

    assert state.repair_attempts["sql_before_schema"] == 1
    assert state.sql_before_schema is False
    assert state.blocked_content == ""


def test_controller_stops_after_kind_budget_is_consumed():
    state = DataRunState(
        requires_fresh_data=True,
        requires_sql_query=True,
        sql_error=True,
        repair_attempts={"sql_error": DATA_REPAIR_BUDGETS["sql_error"]},
    )
    controller = ChatBIRepairController(state)

    assert controller.decide() is None
