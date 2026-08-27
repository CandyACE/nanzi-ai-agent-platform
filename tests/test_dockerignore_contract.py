from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docker_build_excludes_release_artifacts_from_context():
    patterns = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "docker/release/" in patterns or "docker/release/*" in patterns


def test_docker_build_excludes_runtime_and_user_data_from_context():
    patterns = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    for runtime_dir in (
        "data/agent_workspaces/",
        "data/uploads/",
        "data/browser-profiles/",
        "data/branding/",
        "data/generated/",
        "data/generated_files/",
        "data/office_preview_cache/",
        "data/sandbox/",
    ):
        assert runtime_dir in patterns


def test_docker_build_keeps_public_data_docs_for_the_image():
    patterns = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "data/docs/" not in patterns
    assert "data/skills/" not in patterns
