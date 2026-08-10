import pytest

from app.services.saved_report_analysis_service import (
    analyze_saved_report_result,
    render_analysis_markdown,
)


def test_render_analysis_markdown_includes_sections():
    md = render_analysis_markdown(
        report_title="销售日报",
        analysis_payload={
            "key_findings": ["成交额上升"],
            "analysis": ["华南贡献最大"],
            "risk_note": "样本量偏少",
        },
    )
    assert "业务解读" in md
    assert "成交额上升" in md
    assert "华南贡献最大" in md
    assert "样本量偏少" in md


@pytest.mark.asyncio
async def test_analyze_saved_report_result_success_with_stub_generator():
    async def fake_generator(_prompt: str) -> str:
        return '{"key_findings":["结论A","结论B"],"analysis":["分析1","分析2","分析3"],"risk_note":""}'

    result = await analyze_saved_report_result(
        report_title="测试报表",
        original_query="看一下销售",
        parsed_result={"rows": [{"amt": 10}]},
        column_labels={"amt": "成交额"},
        generator=fake_generator,
    )
    assert result["analysis_status"] == "success"
    assert result["analysis"]["key_findings"][0] == "结论A"
    assert "成交" in (result["analysis_markdown"] or "") or "结论A" in (result["analysis_markdown"] or "")
