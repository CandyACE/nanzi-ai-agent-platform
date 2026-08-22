"""沙箱管理（运维/管理）端点。

当前提供 docker 策略沙箱镜像的预构建（预热）以及 E2B/SSH 连接测试能力：

- ``GET  /admin/sandbox/docker/prebuild-status``：查询 docker 沙箱镜像是否已预构建
  以及当前后端是否具备自动构建能力（仅本地 inspect，不触发构建）。
- ``POST /admin/sandbox/docker/prebuild``：执行一次镜像预构建，使运行时
  docker 沙箱首次创建时不需现场构建（分钟级）而直接命中缓存（秒级）。
- ``POST /sandbox/docker/workspace/ensure``：当前登录用户手动启动或复用自己的
  Docker 工作区容器，不执行用户命令。
- ``GET  /sandbox/docker/workspace/status``：只读查询当前登录用户的 Docker
  工作区容器状态，不触发初始化。
- ``POST /admin/sandbox/{e2b|ssh}/test-connection``：按管理页面当前填写的配置
  初始化一次真实沙箱，完成连通性/初始化检查后立即释放资源。

这些端点都挂在 ``v1_secured`` 下（继承 ``require_api_key`` +
``verify_v1_api_access``）。镜像预构建和 E2B/SSH 连通性测试额外校验
``role == "admin"``；用户工作区 ensure 接口只使用当前登录用户身份。
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.dependencies import require_api_key
from app.schemas.response import StandardResponse
from app.services.ai.runtime.agentscope.docker_prebuild import (
    docker_workspace_prebuild_status,
    prebuild_docker_workspace_image,
)
from app.services.ai.runtime.agentscope.workspace import (
    DockerSandboxUnavailableError,
    build_sandbox_workspace_for_test,
    docker_workspace_status as docker_workspace_status_runtime,
    docker_workspace_runtime_metadata,
    ensure_docker_workspace as ensure_docker_workspace_runtime,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_admin(user_info: Dict[str, Any]) -> None:
    """普通 API 用户无权执行沙箱管理操作。"""
    role = user_info.get("role") or user_info.get("user_role")
    if role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行沙箱管理操作")


@router.get(
    "/admin/sandbox/docker/prebuild-status",
    response_model=StandardResponse[Dict[str, Any]],
    summary="查询 Docker 沙箱镜像是否已预构建",
)
async def get_docker_prebuild_status(
    user_info: Dict[str, Any] = Depends(require_api_key),
):
    """查询 Docker 镜像缓存和自动构建能力，离线时返回手动下载信息。"""
    _require_admin(user_info)
    status = await docker_workspace_prebuild_status()
    return StandardResponse(
        data=status,
        message=status.get("message") or "success",
    )


@router.post(
    "/admin/sandbox/docker/prebuild",
    response_model=StandardResponse[Dict[str, Any]],
    summary="预构建 Docker 沙箱镜像（预热）",
)
async def trigger_docker_prebuild(
    user_info: Dict[str, Any] = Depends(require_api_key),
):
    """强制构建（或复用已存在）Docker 沙箱基础镜像。

    流程与运行时 ``DockerWorkspace._build_or_reuse_image`` 完全一致，tag 也完全
    一致；幂等：镜像已存在则直接返回 ``reused=True`` 不重复构建。构建成功后写入
    配置标记 ``sandbox_docker_prebuild_done``。

    注意：这是一个**同步**长耗时操作（首次构建分钟级），会阻塞当前请求直到完成。
    如果后端无法访问 Docker daemon，则返回 ``action=manual_download`` 和镜像导入
    信息，不会把环境不支持误报成构建失败。
    """
    _require_admin(user_info)
    try:
        result = await prebuild_docker_workspace_image(force=False)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return StandardResponse(
        data=result,
        message=result.get("message")
        if result.get("action") == "manual_download"
        else "success",
    )


class DockerWorkspaceEnsureRequest(BaseModel):
    """当前用户手动启动 Docker 工作区所需的会话标识。"""

    conversation_id: str


@router.post(
    "/sandbox/docker/workspace/ensure",
    response_model=StandardResponse[Dict[str, Any]],
    summary="启动或复用当前用户的 Docker 沙箱容器",
)
async def ensure_docker_workspace_endpoint(
    body: DockerWorkspaceEnsureRequest,
    user_info: Dict[str, Any] = Depends(require_api_key),
):
    """只确保当前用户容器运行，不在容器内执行用户命令。"""
    conversation_id = body.conversation_id.strip()
    if not conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id 不能为空")

    try:
        workspace = await ensure_docker_workspace_runtime(
            user_id=user_info.get("user_id") or user_info.get("id"),
            user_name=user_info.get("user_name") or user_info.get("username"),
            user_info=user_info,
            conversation_id=conversation_id,
        )
    except DockerSandboxUnavailableError as exc:
        status_code = (
            409
            if exc.reason_code == "docker_policy_not_effective"
            else 503
        )
        raise HTTPException(
            status_code=status_code,
            detail={
                "reason_code": exc.reason_code,
                "message": exc.user_message,
            },
        ) from exc

    return StandardResponse(
        data=docker_workspace_runtime_metadata(workspace),
        message="Docker 沙箱容器已运行。",
    )


@router.get(
    "/sandbox/docker/workspace/status",
    response_model=StandardResponse[Dict[str, Any]],
    summary="查询当前用户的 Docker 沙箱容器状态",
)
async def get_docker_workspace_status_endpoint(
    conversation_id: str = Query(..., min_length=1),
    user_info: Dict[str, Any] = Depends(require_api_key),
):
    """只查询当前用户容器，不触发 DockerWorkspace 初始化。"""
    conversation_id = conversation_id.strip()
    if not conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id 不能为空")

    try:
        status = await docker_workspace_status_runtime(
            user_id=user_info.get("user_id") or user_info.get("id"),
            user_name=user_info.get("user_name") or user_info.get("username"),
            user_info=user_info,
            conversation_id=conversation_id,
        )
    except DockerSandboxUnavailableError as exc:
        status_code = 409 if exc.reason_code == "docker_policy_not_effective" else 503
        raise HTTPException(
            status_code=status_code,
            detail={
                "reason_code": exc.reason_code,
                "message": exc.user_message,
            },
        ) from exc

    return StandardResponse(
        data=status,
        message="Docker 沙箱状态查询完成。",
    )


class SandboxConnectionTestRequest(BaseModel):
    """E2B/SSH 连接测试所需的临时配置覆盖值。

    密钥字段允许接收管理页面的脱敏值；运行时会识别 ``****`` 并回退到服务端
    已保存的真实配置，避免页面在未修改密钥时把脱敏文本当成凭据。
    """

    sandbox_e2b_api_key: str = ""
    sandbox_e2b_template: str = ""
    sandbox_e2b_timeout_seconds: str = "300"
    sandbox_ssh_host: str = ""
    sandbox_ssh_port: str = "22"
    sandbox_ssh_user: str = ""
    sandbox_ssh_auth_type: str = "password"
    sandbox_ssh_password: str = ""
    sandbox_ssh_private_key: str = ""
    sandbox_ssh_remote_workdir: str = "/workspace"


@router.post(
    "/admin/sandbox/{policy}/test-connection",
    response_model=StandardResponse[Dict[str, Any]],
    summary="测试 E2B/SSH 沙箱连接",
)
async def test_sandbox_connection(
    policy: Literal["e2b", "ssh"],
    body: SandboxConnectionTestRequest,
    user_info: Dict[str, Any] = Depends(require_api_key),
):
    """使用当前页面配置做一次真实初始化测试，并在结束后释放沙箱。"""
    _require_admin(user_info)
    workspace = None
    try:
        workspace = await build_sandbox_workspace_for_test(
            policy,
            body.model_dump(),
        )
        return StandardResponse(
            data={"policy": policy, "connected": True},
            message=f"{policy.upper()} 沙箱连接测试成功",
        )
    except Exception as exc:
        # 不记录请求体，避免 API Key、密码或私钥进入日志；异常文本仅用于向管理员
        # 说明远端返回的可诊断错误。
        detail = str(exc).strip() or "远端返回未知错误"
        logger.warning(
            "沙箱连接测试失败 policy=%s error_type=%s",
            policy,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail=f"{policy.upper()} 沙箱连接测试失败：{detail}",
        ) from exc
    finally:
        if workspace is not None:
            close = getattr(workspace, "close", None)
            if callable(close):
                try:
                    result = close()
                    if inspect.isawaitable(result):
                        await result
                except Exception as exc:
                    logger.warning(
                        "沙箱连接测试资源释放失败 policy=%s error_type=%s",
                        policy,
                        type(exc).__name__,
                    )
