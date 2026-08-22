#!/usr/bin/env python3
"""Docker 沙箱镜像预构建与调试脚本 (Docker Sandbox Prebuild & Proxy Utility).

支持在宿主机或容器内部直接执行构建，支持配置 HTTP/HTTPS 代理、自定义基础镜像、实时查看 Docker 构建日志，
并在构建成功后自动更新系统配置与预构建状态标记。

使用方式:
  1. 本地/容器内直接构建（推荐，实时查看 Docker build 日志）:
     python scripts/prebuild_docker_sandbox.py --base-image python:3.11-slim
     
  2. 带代理构建:
     python scripts/prebuild_docker_sandbox.py --base-image python:3.11-slim --proxy http://127.0.0.1:7890
     # 或通过系统环境变量自动识别:
     export HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890
     python scripts/prebuild_docker_sandbox.py

  3. 仅检查当前预构建状态与 Tag:
     python scripts/prebuild_docker_sandbox.py --status --base-image python:3.11-slim

  4. 强制重新构建（忽略本地缓存）:
     python scripts/prebuild_docker_sandbox.py --force --base-image python:3.11-slim

  5. 通过平台 HTTP 管理接口触发构建:
     python scripts/prebuild_docker_sandbox.py --api-url http://localhost:8000 --api-key <ADMIN_API_KEY>
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any

# 确保项目根目录在 sys.path 中
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


async def check_status_cli(base_image: str | None) -> None:
    """查询 Docker 沙箱镜像预构建状态。"""
    from app.services.ai.runtime.agentscope.docker_prebuild import docker_workspace_prebuild_status

    print("\n🔍 正在检查 Docker 沙箱镜像状态...")
    status = await docker_workspace_prebuild_status(base_image=base_image)
    
    print("=" * 60)
    print(f"  基础镜像 (Base Image):     {base_image or '(默认配置)'}")
    print(f"  计算 Tag:                  {status.get('tag') or '无法计算'}")
    print(f"  Docker Daemon 状态:        {'🟢 可连接' if status.get('docker_available') else '🔴 不可达'}")
    print(f"  镜像预构建就绪 (Prebuilt): {'✅ 已就绪 (秒级拉起)' if status.get('prebuilt') else '⏳ 尚未预构建'}")
    print(f"  状态说明:                  {status.get('message')}")
    print("=" * 60)


async def prebuild_direct(
    base_image: str | None,
    force: bool = False,
    proxy: str | None = None,
) -> None:
    """在当前环境直接使用 aiodocker / Docker API 执行构建并输出实时日志。"""
    import aiodocker
    from app.services.ai.runtime.agentscope.docker_prebuild import (
        _prepare_context,
        _mark_prebuilt,
        _image_exists,
        check_docker_daemon,
        DEFAULT_DOCKER_BASE_IMAGE,
    )

    effective_base = (base_image or DEFAULT_DOCKER_BASE_IMAGE).strip()
    print("\n" + "=" * 65)
    print("🚀 开始执行 Docker 沙箱镜像预构建")
    print(f"   - 基础镜像: {effective_base}")
    print(f"   - 强制重建 (Force): {'是' if force else '否（若存在则直接复用）'}")

    # 代理处理
    build_args: dict[str, str] = {}
    http_proxy = proxy or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy")

    if http_proxy:
        build_args["HTTP_PROXY"] = http_proxy
        build_args["http_proxy"] = http_proxy
        print(f"   - HTTP 代理: {http_proxy}")
    if https_proxy:
        build_args["HTTPS_PROXY"] = https_proxy
        build_args["https_proxy"] = https_proxy
        print(f"   - HTTPS 代理: {https_proxy}")
    if no_proxy:
        build_args["NO_PROXY"] = no_proxy
        build_args["no_proxy"] = no_proxy
        print(f"   - NO_PROXY: {no_proxy}")
    print("=" * 65 + "\n")

    # 1. 检查 Docker daemon
    daemon_status = await check_docker_daemon(aiodocker)
    if not daemon_status["available"]:
        print(f"❌ 无法连接 Docker Daemon: {daemon_status.get('message')}")
        if daemon_status.get("error"):
            print(f"   详细错误: {daemon_status['error']}")
        sys.exit(1)

    print("🟢 Docker Daemon 连接正常")

    # 2. 生成构建上下文
    ctx_dir: str | None = None
    client: Any | None = None
    try:
        print("📦 正在生成 AgentScope Docker 构建上下文...")
        ctx_dir, tag = await _prepare_context(effective_base)
        print(f"🎯 目标构建 Tag: {tag}")
        print(f"📂 临时上下文目录: {ctx_dir}")

        client = aiodocker.Docker()

        # 3. 检查缓存
        if not force and await _image_exists(client, tag):
            print(f"\n✨ 镜像缓存命中！镜像 [{tag}] 已存在于本地 Docker 中，无需重新构建。")
            await _mark_prebuilt(effective_base)
            print("✅ 已同步将预构建完成状态写入系统配置表。")
            return

        # 4. 打包构建上下文
        print("🗜️ 正在压缩打包构建上下文 (tar)...")
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w") as tf:
            tf.add(ctx_dir, arcname=".")
        tar_buf.seek(0)

        # 5. 执行构建并流式输出日志
        print("🔨 正在向 Docker Daemon 提交构建任务，请等待（日志实时输出中）...\n" + "-" * 65)

        build_params: dict[str, Any] = {
            "fileobj": tar_buf,
            "tag": tag,
            "stream": True,
            "rm": True,
            "encoding": "identity",
        }
        if build_args:
            build_params["buildargs"] = build_args

        async for chunk in client.images.build(**build_params):
            if isinstance(chunk, dict):
                stream_text = chunk.get("stream") or chunk.get("status")
                if stream_text and isinstance(stream_text, str):
                    sys.stdout.write(stream_text)
                    sys.stdout.flush()
                error = chunk.get("error") or chunk.get("errorDetail")
                if error:
                    msg = error.get("message") if isinstance(error, dict) else str(error)
                    print(f"\n❌ Docker 构建失败: {msg}")
                    sys.exit(1)

        print("-" * 65)
        print(f"\n🎉 镜像 [{tag}] 构建成功！")
        
        # 6. 标记完成并持久化
        print("💾 正在更新系统配置与预构建状态标记...")
        await _mark_prebuilt(effective_base)
        print("✅ 状态已成功写入平台主库和 Redis 缓存！")
        print("👉 现在您可以在前端系统配置或聊天沙箱中秒级启动 Docker 策略容器。\n")

    except Exception as exc:
        print(f"\n❌ 构建过程中发生异常: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if ctx_dir:
            shutil.rmtree(ctx_dir, ignore_errors=True)
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass


async def trigger_via_http(
    api_url: str,
    api_key: str,
    base_image: str | None = None,
) -> None:
    """通过 HTTP API 触发预构建接口。"""
    import urllib.parse
    import urllib.request
    import json

    base = api_url.rstrip("/")
    params = {}
    if base_image:
        params["base_image"] = base_image.strip()
    query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{base}/api/v1/admin/sandbox/docker/prebuild{query_str}"

    print(f"\n🌐 正在向平台管理接口发送预构建请求: POST {url}")
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key.strip(),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            resp_body = resp.read().decode("utf-8")
            data = json.loads(resp_body)
            print("=" * 60)
            print(f"HTTP 响应状态码: {resp.status}")
            print(f"返回数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
            print("=" * 60)
            if data.get("code") == 200:
                print("\n🎉 通过 HTTP 接口触发预构建成功！")
            else:
                print(f"\n⚠️ 接口返回非 200 结果: {data.get('message')}")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        print(f"❌ HTTP 请求失败: {exc.code} {exc.reason}\n{err_body}")
        sys.exit(1)
    except Exception as exc:
        print(f"❌ 请求异常: {exc}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Docker 沙箱镜像预构建与代理支持运维脚本",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--base-image",
        type=str,
        default="python:3.11-slim",
        help="指定 Docker 基础镜像 (例如 python:3.11-slim 或阿里云加速镜像)",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="指定构建时使用的 HTTP/HTTPS 代理 (如 http://127.0.0.1:7890)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新构建（忽略本地已存在的镜像缓存）",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="仅检查当前基础镜像的预构建状态与 Tag，不执行构建",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=None,
        help="通过平台的 HTTP API 触发预构建 (例如 http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="通过 HTTP API 触发时附带的管理员 API Key (X-API-Key)",
    )

    args = parser.parse_args()

    if args.status:
        asyncio.run(check_status_cli(base_image=args.base_image))
    elif args.api_url:
        if not args.api_key:
            print("❌ 使用 --api-url 模式时必须通过 --api-key 提供管理员 API Key！")
            sys.exit(1)
        asyncio.run(
            trigger_via_http(
                api_url=args.api_url,
                api_key=args.api_key,
                base_image=args.base_image,
            )
        )
    else:
        asyncio.run(
            prebuild_direct(
                base_image=args.base_image,
                force=args.force,
                proxy=args.proxy,
            )
        )


if __name__ == "__main__":
    main()
