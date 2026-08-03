from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docker_build_excludes_release_artifacts_from_context():
    patterns = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "docker/release/" in patterns or "docker/release/*" in patterns
