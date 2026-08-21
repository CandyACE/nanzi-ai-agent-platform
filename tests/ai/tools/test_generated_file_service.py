from pathlib import Path
from datetime import timedelta

import pytest


pytestmark = pytest.mark.no_infrastructure


def test_generated_file_default_ttl_is_one_week():
    from app.services.ai.tools.generated_file_service import DEFAULT_TTL

    assert DEFAULT_TTL == timedelta(days=7)


def test_publish_generates_private_artifact_and_resolves_matching_token(tmp_path, monkeypatch):
    from app.services.ai.tools import generated_file_service

    monkeypatch.setattr(generated_file_service, "generated_files_root", lambda: tmp_path)
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"workbook")

    artifact = generated_file_service.publish(source, "report.xlsx")

    assert artifact.download_url.startswith("/api/v1/chat/generated-files/")
    assert "static/uploads" not in artifact.download_url
    resolved = generated_file_service.resolve_for_download(
        artifact.artifact_id,
        artifact.token,
    )
    assert resolved is not None
    assert resolved.path.read_bytes() == b"workbook"


def test_publish_uses_configured_public_url_for_download_link(tmp_path, monkeypatch):
    from app.services.ai.tools import generated_file_service

    monkeypatch.setattr(generated_file_service, "generated_files_root", lambda: tmp_path)
    monkeypatch.setattr(
        generated_file_service.settings,
        "APP_PUBLIC_URL",
        "https://files.example.com/",
    )
    source = tmp_path / "report.md"
    source.write_text("# report", encoding="utf-8")

    artifact = generated_file_service.publish(source, "report.md")

    assert artifact.download_url.startswith(
        "https://files.example.com/api/v1/chat/generated-files/"
    )
    assert "//api/" not in artifact.download_url


@pytest.mark.asyncio
async def test_system_download_url_prefix_takes_precedence_over_env(monkeypatch):
    from app.services.ai.tools import generated_file_service

    async def fake_get(key, default=None):
        assert key == "download_url_prefix"
        return "https://configured.example.com/"

    monkeypatch.setattr(generated_file_service.ConfigService, "get", fake_get)
    monkeypatch.setattr(
        generated_file_service.settings,
        "APP_PUBLIC_URL",
        "https://environment.example.com",
    )

    assert await generated_file_service.get_download_url_prefix() == "https://configured.example.com"


def test_resolve_for_download_rejects_wrong_token(tmp_path, monkeypatch):
    from app.services.ai.tools import generated_file_service

    monkeypatch.setattr(generated_file_service, "generated_files_root", lambda: tmp_path)
    source = tmp_path / "source.docx"
    source.write_bytes(b"document")
    artifact = generated_file_service.publish(source, "letter.docx")

    assert generated_file_service.resolve_for_download(artifact.artifact_id, "wrong") is None
