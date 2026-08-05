"""Contract: pytest must not flush shared Redis unless TEST_REDIS_FLUSH is set."""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[1]
CONFTEST = ROOT / "tests" / "conftest.py"


def _load_conftest_helpers():
    spec = importlib.util.spec_from_file_location("nanzi_test_conftest", CONFTEST)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_conftest_does_not_unconditionally_flushdb():
    text = CONFTEST.read_text(encoding="utf-8")
    assert "_should_flush_redis_for_tests" in text
    assert "TEST_REDIS_FLUSH" in text
    assert "await r.flushdb()" in text
    assert "if _should_flush_redis_for_tests()" in text


def test_should_flush_redis_flag_parsing(monkeypatch):
    module = _load_conftest_helpers()
    monkeypatch.delenv("TEST_REDIS_FLUSH", raising=False)
    assert module._should_flush_redis_for_tests() is False
    monkeypatch.setenv("TEST_REDIS_FLUSH", "1")
    assert module._should_flush_redis_for_tests() is True
    monkeypatch.setenv("TEST_REDIS_FLUSH", "true")
    assert module._should_flush_redis_for_tests() is True
    monkeypatch.setenv("TEST_REDIS_FLUSH", "0")
    assert module._should_flush_redis_for_tests() is False
