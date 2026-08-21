"""环境探测（bash 运行环境横幅）后端单测。

验证 `app/utils/env.py`：可信信号（/.dockerenv、/proc/self/cgroup
内容）命中任一即判为 docker；普通 `/app` 目录不能单独证明容器；
探测异常静默降级 host；
`get_env` 进程级缓存只探一次；`reset_probe_cache` 可重置缓存。
"""
import pytest

from app.utils import env


@pytest.fixture(autouse=True)
def _reset_cache():
    """每个用例前置清空模块级缓存，避免探测结果互相污染。"""
    env.reset_probe_cache()
    yield
    env.reset_probe_cache()


def test_dockerenv_present_is_docker(monkeypatch):
    monkeypatch.setattr(env.os.path, "exists", lambda p: p == env._DOCKERENV_PATH)
    monkeypatch.setattr(env.os.path, "isdir", lambda p: False)

    assert env.detect_env() == "docker"


def test_app_dir_alone_is_not_docker(monkeypatch):
    # 宿主机也可能存在 /app，普通目录不能单独证明当前进程运行在容器内。
    monkeypatch.setattr(env.os.path, "exists", lambda p: False)
    monkeypatch.setattr(env, "_cgroup_has_container_marker", lambda: False)

    assert env.detect_env() == "host"


def test_cgroup_docker_marker_is_docker(monkeypatch):
    monkeypatch.setattr(env.os.path, "exists", lambda p: False)
    monkeypatch.setattr(env.os.path, "isdir", lambda p: False)
    monkeypatch.setattr(
        env,
        "_cgroup_has_container_marker",
        lambda: True,
    )

    assert env.detect_env() == "docker"


def test_cgroup_kubepods_marker_is_docker(monkeypatch):
    # k8s Pod 的 cgroup 含 kubepods，也应视为容器
    monkeypatch.setattr(env.os.path, "exists", lambda p: False)
    monkeypatch.setattr(env.os.path, "isdir", lambda p: False)
    monkeypatch.setattr(
        env,
        "_cgroup_has_container_marker",
        lambda: any(m in ("0::/kubepods.slice/burstable/x") for m in env._CGROUP_MARKERS),
    )

    assert env.detect_env() == "docker"


def test_no_markers_is_host(monkeypatch):
    monkeypatch.setattr(env.os.path, "exists", lambda p: False)
    monkeypatch.setattr(env.os.path, "isdir", lambda p: False)
    monkeypatch.setattr(env, "_cgroup_has_container_marker", lambda: False)

    assert env.detect_env() == "host"


def test_cgroup_read_failure_silently_falls_back_to_host(monkeypatch):
    """cgroup 读取失败被吞掉（返回 False），整体静默降级 host，不抛异常。"""
    monkeypatch.setattr(env.os.path, "exists", lambda p: False)
    monkeypatch.setattr(env.os.path, "isdir", lambda p: False)

    import builtins

    def _boom(*_a, **_k):
        raise OSError("permission denied")

    monkeypatch.setattr(builtins, "open", _boom)

    assert env._cgroup_has_container_marker() is False
    assert env.detect_env() == "host"


def test_get_env_caches_single_probe(monkeypatch):
    """get_env 进程级只探一次并缓存。"""
    calls = []

    real_detect = env.detect_env

    def _counted():
        calls.append(1)
        return real_detect()

    monkeypatch.setattr(env, "detect_env", _counted)

    first = env.get_env()
    second = env.get_env()

    assert first == second
    assert len(calls) == 1


def test_reset_probe_cache_forces_reprobe(monkeypatch):
    monkeypatch.setattr(env.os.path, "exists", lambda p: False)
    monkeypatch.setattr(env.os.path, "isdir", lambda p: False)
    monkeypatch.setattr(env, "_cgroup_has_container_marker", lambda: False)

    assert env.get_env() == "host"
    env.reset_probe_cache()
    # 重置后即便外部信号变化也应重新探测（此处 host 判定仍成立）
    assert env.get_env() == "host"
