"""运行环境探测：判断当前后端进程跑在容器（Docker / k8s Pod）还是宿主机。

Bash 工具由后端进程直接 `subprocess` 执行（`CancellableLocalBackend`），因此
「Bash 跑在哪」==「后端跑在哪」，是进程级恒定值。本模块基于文件系统特征在
首次调用时探测一次并缓存，供 SSE 事件流把结果下发给前端用于环境风险横幅。
"""
from __future__ import annotations

import os
from typing import Literal

EnvKind = Literal["docker", "host"]

# cgroup 中的容器标记：docker 与 k8s Pod（kubepods）都视为容器，避免误标为宿主机
_CGROUP_MARKERS = ("docker", "kubepods")
_DOCKERENV_PATH = "/.dockerenv"

_cache: EnvKind | None = None


def _cgroup_has_container_marker() -> bool:
    """读 /proc/self/cgroup，命中 docker/kubepods 即视为容器。"""
    try:
        with open("/proc/self/cgroup", "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
    except OSError:
        return False
    return any(marker in content for marker in _CGROUP_MARKERS)


def detect_env() -> EnvKind:
    """判定当前环境为容器还是宿主机。

    - 存在 `/.dockerenv` 或 cgroup 含 docker/kubepods → ``docker``
    - 其余（含探测异常）→ ``host``（静默降级，由调用方记录 debug 日志）
    """
    if os.path.exists(_DOCKERENV_PATH):
        return "docker"
    if _cgroup_has_container_marker():
        return "docker"
    return "host"


def get_env() -> EnvKind:
    """返回探测结果，进程级只探一次并缓存。"""
    global _cache
    if _cache is None:
        _cache = detect_env()
    return _cache


def reset_probe_cache() -> None:
    """清空进程级缓存（主要供测试重置状态）。"""
    global _cache
    _cache = None
