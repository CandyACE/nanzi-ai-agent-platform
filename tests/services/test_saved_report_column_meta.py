from app.services.saved_report_column_meta import (
    build_column_meta_from_names,
    column_labels_from_meta,
    extract_result_column_names,
    extract_sql_alias_map,
    fill_missing_terms_with_heuristics,
    heuristic_term_for_column,
    merge_column_meta,
)


def test_extract_result_column_names_from_rows():
    parsed = {"rows": [{"cust_cnt": 1, "city": "深圳"}]}
    assert extract_result_column_names(parsed) == ["cust_cnt", "city"]


def test_merge_column_meta_live_overrides_snapshot_term():
    snapshot = {
        "version": 1,
        "source": "save_time",
        "columns": [{"name": "cust_cnt", "term": "旧客户数"}],
    }
    live = build_column_meta_from_names(
        ["cust_cnt", "city"],
        term_map={"cust_cnt": "客户数", "city": "城市"},
        source="execute_refresh",
    )
    merged = merge_column_meta(snapshot, live)
    assert merged is not None
    labels = column_labels_from_meta(merged)
    assert labels["cust_cnt"] == "客户数"
    assert labels["city"] == "城市"


def test_merge_column_meta_falls_back_to_snapshot_when_live_missing_term():
    snapshot = {
        "version": 1,
        "source": "save_time",
        "columns": [{"name": "city", "term": "城市"}],
    }
    live = build_column_meta_from_names(["city", "amt"], source="execute_refresh")
    merged = merge_column_meta(snapshot, live)
    labels = column_labels_from_meta(merged)
    assert labels["city"] == "城市"
    assert "amt" not in labels or labels.get("amt") in (None, "")


def test_heuristic_term_for_register_count():
    assert heuristic_term_for_column("register_count") == "注册数量"


def test_fill_missing_terms_uses_sql_alias_and_heuristics():
    meta = build_column_meta_from_names(["register_count", "created_month"], source="save_time")
    filled = fill_missing_terms_with_heuristics(
        meta,
        sql="SELECT count(*) AS register_count, toYYYYMM(created_at) AS created_month FROM users",
        term_map={"created_at": "创建时间"},
    )
    labels = column_labels_from_meta(filled)
    assert labels["register_count"] == "注册数量"
    # created_month 可能启发为 创建月份，或由 alias 映射到 创建时间
    assert labels.get("created_month") in {"创建月份", "创建时间"}


def test_extract_sql_alias_map():
    aliases = extract_sql_alias_map(
        "SELECT count(1) AS register_count, city_name AS city FROM t GROUP BY 2"
    )
    assert "register_count" in aliases
    assert "city" in aliases
