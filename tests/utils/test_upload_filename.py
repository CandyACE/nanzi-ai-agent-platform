import re
import uuid

import pytest

from app.utils import fs_access
from app.utils.fs_access import build_upload_storage_name, open_upload_storage_file

pytestmark = pytest.mark.no_infrastructure


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


def test_open_upload_storage_file_retries_after_a_name_collision(tmp_path, monkeypatch):
    suffixes = iter(
        (
            uuid.UUID("a1b20000-0000-0000-0000-000000000000"),
            uuid.UUID("a1b20000-0000-0000-0000-000000000000"),
            uuid.UUID("c3d40000-0000-0000-0000-000000000000"),
        )
    )
    monkeypatch.setattr(fs_access.uuid, "uuid4", lambda: next(suffixes))

    first_path, first_handle = open_upload_storage_file(str(tmp_path), "report.csv")
    with first_handle:
        first_handle.write(b"first")

    second_path, second_handle = open_upload_storage_file(str(tmp_path), "report.csv")
    with second_handle:
        second_handle.write(b"second")

    assert first_path != second_path
    assert (tmp_path / "report_a1b2.csv").read_bytes() == b"first"
    assert (tmp_path / "report_c3d4.csv").read_bytes() == b"second"
