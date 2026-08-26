"""Regression tests for the Python environment bootstrap in dev.sh."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _prepare_fake_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    (repo / "frontend").mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()
    shutil.copy(ROOT / "dev.sh", repo / "dev.sh")
    (repo / "requirements.txt").write_text("example-package==1.0\n", encoding="utf-8")
    (repo / "frontend" / "package.json").write_text("{}\n", encoding="utf-8")
    (repo / ".env").write_text(
        "DATABASE_TYPE=postgresql\n"
        "POSTGRES_HOST=pg.example.internal\n"
        "POSTGRES_PORT=5432\n"
        "POSTGRES_DB=nanzi_test\n"
        "REDIS_HOST=redis.example.internal\n"
        "REDIS_PORT=6380\n"
        "REDIS_DB=4\n",
        encoding="utf-8",
    )
    return repo, fake_bin, home


def _install_fake_commands(fake_bin: Path, home: Path, *, uv_in_path: bool) -> None:
    uv_source = fake_bin / "uv-source"
    _write_executable(
        uv_source,
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$HOME/uv.log"

case "${1:-}" in
  python)
    exit 0
    ;;
  venv)
    target=""
    clear=false
    for arg in "$@"; do
      if [ "$arg" = "--clear" ]; then
        clear=true
      elif [ "$arg" != "venv" ] && [ "$arg" != "--python" ] && [ "$arg" != "3.11" ] && [ "${arg#-}" = "$arg" ]; then
        target="$arg"
      fi
    done
    if [ "$clear" = true ]; then
      rm -rf "$target"
    fi
    mkdir -p "$target/bin"
    printf '%s\n' '#!/bin/sh' \
      'if [ "${1:-}" = "-c" ]; then printf "%s\\n" "3.11"; fi' \
      'exit 0' > "$target/bin/python"
    chmod +x "$target/bin/python"
    ;;
  pip)
    exit 0
    ;;
  *)
    exit 1
    ;;
esac
""",
    )
    if uv_in_path:
        shutil.copy(uv_source, fake_bin / "uv")
        (fake_bin / "uv").chmod(0o755)

    _write_executable(
        fake_bin / "curl",
        """#!/bin/sh
set -eu
printf '%s\\n' curl >> "$HOME/installer.log"
printf '%s\\n' 'mkdir -p "$HOME/.local/bin"' \
  'cp "$FAKE_UV_SOURCE" "$HOME/.local/bin/uv"' \
  'chmod +x "$HOME/.local/bin/uv"'
""",
    )
    _write_executable(fake_bin / "npm", """#!/bin/sh
printf '%s\\n' npm >> "$HOME/npm.log"
exit 0
""")
    _write_executable(fake_bin / "npx", """#!/bin/sh
printf '%s\\n' npx >> "$HOME/npm.log"
exit 0
""")
    _write_executable(fake_bin / "lsof", """#!/bin/sh
exit 0
""")
    _write_executable(fake_bin / "python3", """#!/bin/sh
exit 0
""")


def _run_dev(repo: Path, fake_bin: Path, home: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "FAKE_UV_SOURCE": str(fake_bin / "uv-source"),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
        }
    )
    return subprocess.run(
        ["bash", str(repo / "dev.sh")],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_dev_sh_bootstraps_uv_python_and_requirements_on_first_run(tmp_path: Path):
    repo, fake_bin, home = _prepare_fake_repo(tmp_path)
    _install_fake_commands(fake_bin, home, uv_in_path=False)

    result = _run_dev(repo, fake_bin, home)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (home / "uv.log").is_file(), result.stdout + result.stderr
    log = (home / "uv.log").read_text(encoding="utf-8")
    assert (home / "installer.log").read_text(encoding="utf-8").strip() == "curl"
    assert "python install 3.11" in log
    assert "venv" in log and "--python 3.11" in log
    assert "pip install" in log and "requirements.txt" in log
    assert (repo / ".venv" / ".requirements.hash").is_file()
    assert "启动环境信息" in result.stdout
    assert "uv: 未安装（启动时自动安装）" in result.stdout
    assert "Python 目标版本: 3.11" in result.stdout
    assert "虚拟环境: .venv" in result.stdout
    assert "PyPI 镜像: https://pypi.tuna.tsinghua.edu.cn/simple" in result.stdout
    assert "DATABASE_TYPE: postgresql" in result.stdout
    assert "数据库地址: pg.example.internal:5432/nanzi_test" in result.stdout
    assert "Redis 地址: redis.example.internal:6380/4" in result.stdout
    assert "[1/4]" in result.stdout


def test_dev_sh_skips_python_install_when_requirements_are_unchanged(tmp_path: Path):
    repo, fake_bin, home = _prepare_fake_repo(tmp_path)
    _install_fake_commands(fake_bin, home, uv_in_path=True)

    first_result = _run_dev(repo, fake_bin, home)
    second_result = _run_dev(repo, fake_bin, home)

    assert first_result.returncode == 0, first_result.stdout + first_result.stderr
    assert second_result.returncode == 0, second_result.stdout + second_result.stderr
    assert (home / "uv.log").is_file(), second_result.stdout + second_result.stderr
    log_lines = (home / "uv.log").read_text(encoding="utf-8").splitlines()
    assert sum(line.startswith("pip install") for line in log_lines) == 1
    assert "后端依赖未变化，跳过安装" in second_result.stdout


def test_dev_sh_rebuilds_existing_non_311_venv(tmp_path: Path):
    repo, fake_bin, home = _prepare_fake_repo(tmp_path)
    _install_fake_commands(fake_bin, home, uv_in_path=True)
    old_python = repo / ".venv" / "bin" / "python"
    old_python.parent.mkdir(parents=True)
    _write_executable(
        old_python,
        """#!/bin/sh
if [ "${1:-}" = "-c" ]; then printf '%s\\n' '3.13'; fi
exit 0
""",
    )

    result = _run_dev(repo, fake_bin, home)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (home / "uv.log").is_file(), result.stdout + result.stderr
    log = (home / "uv.log").read_text(encoding="utf-8")
    assert "venv --clear --python 3.11 .venv" in log
    assert old_python.read_text(encoding="utf-8").find("3.11") >= 0
