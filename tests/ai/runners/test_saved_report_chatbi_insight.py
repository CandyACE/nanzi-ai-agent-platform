from app.services.ai.runners.chatbi.insight_meta import build_saved_report_chatbi_insight_meta


def test_build_saved_report_chatbi_insight_includes_visualize_action():
    insight = build_saved_report_chatbi_insight_meta(
        {
            "columns": ["创建时间", "register_count"],
            "rows": [
                {"创建时间": "2026-07", "register_count": 168},
                {"创建时间": "2026-08", "register_count": 8},
            ],
        },
        sql="SELECT 1",
        dataset_name="demo",
        data_source="default_clickhouse",
        result_id="saved_report_run:1",
    )
    assert insight is not None
    assert insight["version"] == 1
    assert insight["execution"]["row_count"] == 2
    action_ids = {action["id"] for action in insight["actions"]}
    assert "visualize" in action_ids
    assert "trend" in action_ids
