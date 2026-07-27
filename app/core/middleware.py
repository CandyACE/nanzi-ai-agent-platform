import time
import uuid
import json
import asyncio
import gzip
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core import database
from typing import Optional

from app.services.audit_service import AuditService, MAX_AUDIT_TEXT_BYTES


def _decode_captured_response_body(
    body: bytes,
    *,
    content_encoding: Optional[str],
    content_type: Optional[str],
) -> str:
    """将响应体转换成可安全写入审计文本字段的字符串。"""
    if not body:
        return ""

    encoding = (content_encoding or "").split(",", 1)[0].strip().lower()
    payload = body
    if encoding == "gzip" or body.startswith(b"\x1f\x8b"):
        try:
            payload = gzip.decompress(body)
        except (OSError, EOFError):
            return f"<compressed response: {encoding or 'gzip'}, {len(body)} bytes>"
    elif encoding:
        return f"<compressed response: {encoding}, {len(body)} bytes>"

    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type == "application/json" or media_type.startswith("text/"):
        return payload.decode("utf-8", errors="replace").replace("\x00", "")
    return f"<binary response: {len(payload)} bytes>"

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Path Filtering: Only log /api/ requests
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # 2. Trace ID Logic
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.state.trace_id = trace_id
        
        start_time = time.time()
        
        # 3. Process Request & Capture Response Body (Optional chunks capture)
        request_body_str = None
        try:
            content_type = request.headers.get("content-type", "")
            content_length = request.headers.get("content-length")
            
            # Only capture JSON/Text, skip large files or unknown types
            if ("application/json" in content_type or "text/" in content_type) and \
               (not content_length or int(content_length) < 102400): # 100KB limit
                body_bytes = await request.body()
                request_body_str = body_bytes.decode("utf-8", errors="ignore")
                # Truncate if still too long (double safety)
                if len(request_body_str) > 10000:
                    request_body_str = request_body_str[:10000] + "...(truncated)"
        except Exception:
            request_body_str = "<error capturing body>"

        response_body_chunks = []
        captured_response_bytes = 0
        response_content_encoding = None
        response_content_type = None
        
        try:
            response = await call_next(request)
        except Exception as e:
            # Re-raise to let exception handlers catch it
            raise e
            
        # Add Trace ID to headers
        response.headers["X-Trace-Id"] = trace_id
        response_content_encoding = response.headers.get("content-encoding")
        response_content_type = response.headers.get("content-type")

        # Wrap body to capture for audit log
        async def body_iterator(actual_iterator):
            nonlocal captured_response_bytes
            async for chunk in actual_iterator:
                remaining = MAX_AUDIT_TEXT_BYTES - captured_response_bytes
                if remaining > 0:
                    captured_chunk = chunk[:remaining]
                    if captured_chunk:
                        response_body_chunks.append(captured_chunk)
                        captured_response_bytes += len(captured_chunk)
                yield chunk

        original_iterator = response.body_iterator
        response.body_iterator = body_iterator(original_iterator)

        # 4. Immediate async enqueue (Non-blocking)
        # We define a post-response callback to be called later
        async def perform_logging():
            process_time = (time.time() - start_time) * 1000 # ms
            
            # Reconstruct response body
            full_body = b"".join(response_body_chunks)
            response_body = _decode_captured_response_body(
                full_body,
                content_encoding=response_content_encoding,
                content_type=response_content_type,
            )

            user_name = getattr(request.state, "user", {}).get("user_name") if hasattr(request.state, "user") else None
            
            await AuditService.log_request_data(
                trace_id=trace_id,
                user_name=user_name,
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                process_time_ms=process_time,
                client_ip=request.client.host if request.client else None,
                request_params=request_body_str or request.query_params.__str__(),
                response_body=response_body
            )

        # Use asyncio.create_task to ensure it runs even if the client disconnects
        # or use starlette's background task if we want it to be part of the request lifecycle.
        # Given we want maximum performance, create_task is fine as long as we don't leak.
        # Actually, to be safe and standard with FastAPI, we'll stick to BackgroundTask
        # but the content will be just a simple queue put.
        from starlette.background import BackgroundTask
        response.background = BackgroundTask(perform_logging)
            
        return response
