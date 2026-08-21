"""Docker 沙箱镜像预构建（预热）服务。

B 方案（docker 策略提速）的核心：docker 沙箱的镜像 tag 是内容哈希
（Dockerfile + requirements.txt + MCP gateway 脚本 + agentscope 版本 的
确定性哈希）；运行时 ``DockerWorkspace`` 首次使用会现场构建该 tag 的镜像
（分钟级），之后命中该 tag 直接复用，不再重复构建。

本模块提供运维/管理用的一次性预构建函数：提前用**与运行时完全相同**的
``prepare_build_context`` 上下文把镜像构建出来 / 复用已有缓存，并写入配置
标记 ``sandbox_docker_prebuild_done``。这样运行时首次创建 docker 沙箱时
``images.inspect(tag)`` 直接命中缓存，秒级拉起容器，省去首次现场构建的分钟
级等待。

关键一致性约束
------------
预构建必须与 ``agentscope.workspace.DockerWorkspace`` 的镜像 tag 计算严格
一致（否则预构建的镜像对运行时毫无意义）。运行时的 ``_build_or_reuse_image``
用 ``prepare_build_context(base_image=base_image, gateway_home=GATEWAY_HOME,
container_workdir=CONTAINER_WORKDIR, node_version=self.node_version,
extra_pip=self.extra_pip)`` 生成 ``(ctx_dir, tag, copy_files)``，其中平台
docker 策略只配置了 ``base_image``（其余 4 项均为框架默认值：GATEWAY_HOME、
CONTAINER_WORKDIR、node_version=None、extra_pip=None）。因此本模块也以同样
参数调用 ``prepare_build_context``，得到完全相同的 tag 与构建上下文。
"""

from __future__ import annotations

import io
import logging
import shutil
import tarfile
from typing import Any

logger = logging.getLogger(__name__)

PREBUILD_CONFIG_KEY = "sandbox_docker_prebuild_done"


async def _prepare_context() -> tuple[str, str]:
    """按运行时 docker 策略相同参数生成构建上下文，返回 ``(ctx_dir, tag)``。

    ``ctx_dir`` 由调用方负责在 finally 中清理。
    """
    from app.services.config_service import ConfigService
    from agentscope.workspace._docker._make_dockerfile import (
        CONTAINER_WORKDIR,
        GATEWAY_HOME,
        prepare_build_context,
    )

    # 与 _policy_docker_workspace 的取值/传参语义保持一致：
    #   - 配置非空 => 显式传入该 base_image；
    #   - 配置留空  => 不传 base_image，让 prepare_build_context 使用框架默认
    #     DEFAULT_BASE_IMAGE（"python:3.11-slim"）。
    # 注意：绝不能把 None 显式传进去 —— 否则 render_dockerfile 会把
    # ``FROM {base_image}`` 渲染成 ``FROM None``，docker 宽松解析成
    # ``library/None`` 导致构建报 "invalid reference format"。
    base_image = (await ConfigService.get("sandbox_docker_base_image", "")).strip() or None

    ctx_args: dict[str, object] = {
        "gateway_home": GATEWAY_HOME,
        "container_workdir": CONTAINER_WORKDIR,
        "node_version": None,
        "extra_pip": None,
    }
    if base_image:
        ctx_args["base_image"] = base_image

    ctx_dir, tag, _ = prepare_build_context(**ctx_args)
    # ctx_dir 为 pathlib.Path，统一成 str 便于 tarfile.add 处理。
    return str(ctx_dir), tag


async def docker_workspace_image_prebuilt() -> bool:
    """查询 docker 沙箱镜像是否已存在于本地（命中缓存 tag）。

    ``True`` 表示镜像已存在，运行时 docker 策略将秒级拉起；``False`` 表示首次
    使用仍需现场构建。仅做本地 inspect 判断，不触发构建。
    """
    try:
        import aiodocker
    except Exception:
        logger.warning("[docker_prebuild] aiodocker not installed; treat as not prebuilt")
        return False

    client = aiodocker.Docker()
    ctx_dir: str | None = None
    try:
        ctx_dir, tag = await _prepare_context()
        try:
            await client.images.inspect(tag)
            return True
        except Exception:
            return False
    except Exception as exc:
        logger.warning("[docker_prebuild] prebuilt check failed: %s", exc)
        return False
    finally:
        if ctx_dir:
            shutil.rmtree(ctx_dir, ignore_errors=True)
        try:
            await client.close()
        except Exception:
            pass


async def prebuild_docker_workspace_image(*, force: bool = False) -> dict[str, Any]:
    """预构建 docker 沙箱镜像（一次性的运维/预热操作）。

    流程与运行时 ``DockerWorkspace._build_or_reuse_image`` 完全一致：
    ``prepare_build_context`` -> ``images.inspect(tag)`` 命中即幂等跳过；
    未命中则 tar 打包 ``ctx_dir``（``arcname="."``）并以 ``encoding="identity"``
    ``images.build(stream=True, rm=True)`` 构建，异常转 RuntimeError（保留 stream
    尾部日志）。构建成功后写入配置标记 ``sandbox_docker_prebuild_done``。

    Args:
        force: 是否强制重新构建（跳过 inspect 缓存命中判断）。默认 ``False``
            幂等（镜像已存在则直接返回、不重复构建）。

    Returns:
        dict: ``{"reused": bool, "built": bool, "tag": str}``。
            reused=True 表示命中已有镜像，本次未触发构建；built=True 表示本次
            完成了新构建。

    Raises:
        RuntimeError: Docker daemon 不可达，或 docker build 失败（含 build stream
            尾部日志）。
    """
    try:
        import aiodocker
    except ImportError as exc:
        raise RuntimeError("aiodocker 未安装，无法预构建 Docker 镜像") from exc

    await _guard_docker_available(aiodocker)

    client = aiodocker.Docker()
    ctx_dir: str | None = None
    try:
        ctx_dir, tag = await _prepare_context()

        # 命中已有镜像且非 force => 幂等跳过（与运行时 _build_or_reuse_image 相同）。
        if not force and await _image_exists(client, tag):
            logger.info("[docker_prebuild] image cache hit %r, skip build", tag)
            await _mark_prebuilt()
            return {"reused": True, "built": False, "tag": tag}

        logger.info("[docker_prebuild] building image %r", tag)
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w") as tf:
            tf.add(ctx_dir, arcname=".")
        tar_buf.seek(0)
        # encoding="identity" 告诉 aiodocker body 是未压缩的 tar，否则 aiodocker
        # 会对已 tar 的字节再做 gzip，daemon 会拒绝畸形流。
        stream = client.images.build(
            fileobj=tar_buf,
            encoding="identity",
            tag=tag,
            stream=True,
            rm=True,
        )
        tail: list[str] = []
        tail_max = 200
        async for chunk in stream:
            if isinstance(chunk, dict):
                if "stream" in chunk:
                    msg = str(chunk["stream"]).rstrip()
                    if msg:
                        logger.debug("[docker_prebuild] %s", msg)
                        tail.append(msg)
                        if len(tail) > tail_max:
                            del tail[: len(tail) - tail_max]
                if "error" in chunk:
                    log = "\n".join(tail)
                    raise RuntimeError(
                        f"docker build failed: {chunk['error']}\n"
                        f"--- last {len(tail)} build log lines ---\n"
                        f"{log}",
                    )

        await _mark_prebuilt()
        logger.info("[docker_prebuild] image built and marked prebuilt: %r", tag)
        return {"reused": False, "built": True, "tag": tag}
    finally:
        if ctx_dir:
            shutil.rmtree(ctx_dir, ignore_errors=True)
        try:
            await client.close()
        except Exception:
            pass


async def _image_exists(client: Any, tag: str) -> bool:
    """镜像 tag 是否已存在于本地（命中即复用）。"""
    try:
        await client.images.inspect(tag)
        return True
    except Exception:
        return False


async def _mark_prebuilt() -> None:
    """写入 ``sandbox_docker_prebuild_done`` 配置标记（幂等）。"""
    try:
        from app.services.config_service import ConfigService

        await ConfigService.set_config(
            PREBUILD_CONFIG_KEY,
            "true",
            description="Docker 沙箱基础镜像已预构建（预热）；docker 策略首次使用命中缓存、无需现场构建。由预构建操作自动写入。",
            category="sandbox",
            changed_by="system",
            change_reason="docker sandbox image prebuild completed",
        )
    except Exception as exc:
        logger.warning("[docker_prebuild] failed to write prebuild flag: %s", exc)


async def _guard_docker_available(aiodocker: Any) -> None:
    """提前探测 Docker daemon 可用性，给出清晰错误（而非堆栈）。"""
    client = aiodocker.Docker()
    try:
        await client.version()
    except Exception as exc:
        raise RuntimeError(
            "无法连接 Docker daemon，请确认本机 Docker 已启动且当前用户有访问权限。"
            f" 详情：{exc}",
        ) from exc
    finally:
        try:
            await client.close()
        except Exception:
            pass