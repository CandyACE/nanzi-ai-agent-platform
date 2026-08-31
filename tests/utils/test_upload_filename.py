import re

from app.utils.fs_access import build_upload_storage_name


def test_build_upload_storage_name_keeps_chinese_and_uses_short_suffix():
    name = build_upload_storage_name("销售日报 2025.xlsx", suffix="a1B2")

    assert name == "销售日报 2025_a1B2.xlsx"


def test_build_upload_storage_name_removes_path_separators_without_losing_name():
    name = build_upload_storage_name("../报表\\月度.xlsx", suffix="c3D4")

    assert name == ".._报表_月度_c3D4.xlsx"
    assert "/" not in name
    assert "\\" not in name


def test_build_upload_storage_name_generates_four_hex_characters_by_default():
    name = build_upload_storage_name("report.csv")

    assert re.fullmatch(r"report_[0-9a-f]{4}\.csv", name)
