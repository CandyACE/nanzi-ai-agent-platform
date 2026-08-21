# -*- coding: utf-8 -*-
"""SshWorkspace: a remote-sandbox AgentScope workspace driven over SSH.

This module provides a self-contained
:class:`agentscope.workspace.WorkspaceBase` subclass that treats a
remote host reached over the platform host's ``ssh`` CLI as the
sandbox workdir.  It backs the ``ssh`` sandbox policy selected via the
``sandbox_policy`` system config (the different policies are
documented in ``workspace.py``).

Why a plain ``ssh`` subprocess instead of a Python SSH library:

* The platform already ships the system ``ssh``/``sshpass`` CLI and
  does not want to add ``asyncssh``/``paramiko`` as hard runtime
  dependencies.
* Key authentication works out of the box over the CLI (no TTY
  needed); password authentication requires ``sshpass`` (a documented
  external dependency, checked at build time below).
* The blocking ``subprocess`` calls are wrapped in
  ``asyncio.to_thread`` so they never stall the event loop.

Structure:

* :class:`SshWorkspace` implements the full
  :class:`WorkspaceBase` contract (12 abstract methods) on top of the
  platform host's ``ssh`` CLI.
* ``_SSH_INLINE_SERVER`` is a thin stdio FastMCP server (the same
  ``sandbox`` four-tool shape as ``workspace_container_mcp``) that is
  spawned **locally** by the AgentScope gateway and forwards every
  tool call to the remote host through its own ``ssh`` child process.
  Connection parameters are injected through environment variables so
  the inline script needs no remote package installs.

The remote sandbox layout mirrors the container policy: ``workdir``
(the ``sandbox_ssh_remote_workdir`` value, default ``/workspace``)
holds ``data/``, ``skills/`` and ``sessions/``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import json
import logging
import mimetypes
import os
import posixpath
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any

from agentscope.mcp import MCPClient  # type: ignore[attr-defined]
from agentscope.mcp import StdioMCPConfig  # type: ignore[attr-defined]
from agentscope.message import (  # type: ignore[attr-defined]
    Base64Source,
    DataBlock,
    Msg,
    TextBlock,
    ToolResultBlock,
    URLSource,
)
from agentscope.skill import Skill  # type: ignore[attr-defined]
from agentscope.tool import ToolBase  # type: ignore[attr-defined]
from agentscope.workspace import WorkspaceBase  # type: ignore[attr-defined]
from pydantic import AnyUrl

logger = logging.getLogger(__name__)

# Name used for the injected SSH tool server.  Exposed to the model as
# ``<name>::<tool>``, mirroring the container sandbox policy.
SSH_MCP_NAME = "sandbox"

# Working directory inside the remote sandbox (SSH equivalent of the
# container's /workspace).  Overridable per connection.
SSH_REMOTE_WORKDIR = "/workspace"

# Relative layout the workspace manages inside the remote workdir.
_REMOTE_DATA_DIR = "data"
_REMOTE_SKILLS_DIR = "skills"
_REMOTE_SESSIONS_DIR = "sessions"


@dataclass(frozen=True)
class _ExecResult:
    """Captured remote command outcome (mirrors the container policy)."""

    exit_code: int
    stdout: bytes
    stderr: bytes

    def ok(self) -> bool:
        return self.exit_code == 0


def _have_sshpass() -> bool:
    """True when the ``sshpass`` CLI is on the platform host's PATH."""
    return shutil.which("sshpass") is not None


class SshWorkspace(WorkspaceBase):
    """A remote-host sandbox operated through the platform host's SSH CLI.

    All file/command I/O is forwarded to a remote sandbox host over
    ``ssh``.  ``workdir`` (the ``remote_workdir`` value) is the remote
    working directory, so the higher layers that read
    ``workspace.workdir`` keep working unchanged across policies.

    Args:
        workspace_id: Optional stable id (defaults to a fresh uuid).
        host: Remote host (hostname or IP).  Required.
        port: SSH port (default 22).
        user: Remote user.  Empty means "current local user".
        auth_type: ``"password"`` (via ``sshpass``, requires the CLI)
            or ``"key"`` (private key agent/CLI).
        password: Cleartext password used with ``auth_type="password"``.
        private_key: Private key *contents* (PEM) used with
            ``auth_type="key"``; materialized to a temp file that is
            removed on :meth:`close`.
        remote_workdir: Remote sandbox working directory.
        default_mcps: Static MCP servers seeded on first init.
        skill_paths: Local skill paths copied into ``skills/`` on first
            init (mirrors the container policy seeding).
    """

    # ── WorkspaceBase contract fields ───────────────────────────
    workspace_id: str
    workdir: str
    is_alive: bool

    def __init__(
        self,
        *,
        workspace_id: str | None = None,
        host: str,
        port: int = 22,
        user: str = "",
        auth_type: str = "password",
        password: str | None = None,
        private_key: str | None = None,
        remote_workdir: str = SSH_REMOTE_WORKDIR,
        default_mcps: list[MCPClient] | None = None,
        skill_paths: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(workspace_id=workspace_id)
        self.host = host
        self.port = int(port) if port else 22
        self.user = user or ""
        self.auth_type = (auth_type or "password").lower()
        self.password = password or ""
        self.private_key = private_key or ""
        self.remote_workdir = remote_workdir or SSH_REMOTE_WORKDIR
        self.workdir = self.remote_workdir

        # ── seed-only ───────────────────────────────────────────
        self.default_mcps: list[MCPClient] = list(default_mcps or [])
        self.skill_paths: list[str] = list(skill_paths or [])

        # ── runtime state ───────────────────────────────────────
        self.is_alive = False
        self._mcps: list[MCPClient] = []
        self._mcp_lock = asyncio.Lock()
        self._skill_lock = asyncio.Lock()
        # Materialized private key temp file, cleaned in close().
        self._local_key_path: str | None = None
        # Password file used only by the local inline MCP child. Keeping the
        # secret out of that child's environment and argv avoids disclosure
        # through process inspection.
        self._local_password_path: str | None = None
        # Connection args cached after a successful control test.
        self._control_active = False

    # ── connection helpers ──────────────────────────────────────

    def _ssh_args(self) -> list[str]:
        """Base ``ssh`` argument list (without the target command)."""
        args = [
            "ssh",
            "-p", str(self.port),
            # Require a pre-verified known_hosts entry.  TOFU/disabled host
            # verification is not acceptable for a remote code sandbox.
            "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=30",
            "-o", "BatchMode=yes" if self.auth_type == "key" else "BatchMode=no",
        ]
        if self.auth_type == "key" and self._local_key_path:
            args += ["-i", self._local_key_path]
        return args

    def _build_ssh_command(
        self,
        remote_args: list[str],
        *,
        password_fd: int | None = None,
    ) -> list[str]:
        """Build an SSH argv without ever placing the password in argv."""
        command = self._ssh_args() + [self._target(), *remote_args]
        if self.auth_type == "password":
            if password_fd is None:
                raise ValueError("password SSH commands require a password fd")
            return ["sshpass", "-d", str(password_fd), *command]
        return command

    def _run_remote_sync(
        self,
        remote_args: list[str],
        *,
        input_data: bytes | None = None,
        timeout: float = 600,
    ) -> subprocess.CompletedProcess:
        """Run one SSH command, feeding sshpass through an inherited fd."""
        password_read_fd: int | None = None
        password_write_fd: int | None = None
        process: subprocess.Popen | None = None
        command: list[str] = []
        try:
            if self.auth_type == "password":
                password_read_fd, password_write_fd = os.pipe()
            command = self._build_ssh_command(
                remote_args,
                password_fd=password_read_fd,
            )
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(password_read_fd,) if password_read_fd is not None else (),
            )
            if password_write_fd is not None:
                with os.fdopen(password_write_fd, "wb") as password_stream:
                    password_stream.write(self.password.encode("utf-8") + b"\n")
                    password_stream.flush()
                password_write_fd = None
            if password_read_fd is not None:
                os.close(password_read_fd)
                password_read_fd = None

            stdout, stderr = process.communicate(input=input_data, timeout=timeout)
            return subprocess.CompletedProcess(
                command,
                process.returncode,
                stdout,
                stderr,
            )
        except subprocess.TimeoutExpired:
            if process is None:
                return subprocess.CompletedProcess(command, -1, b"", b"timed out")
            process.kill()
            stdout, stderr = process.communicate()
            return subprocess.CompletedProcess(command, -1, stdout, stderr)
        finally:
            for fd in (password_read_fd, password_write_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass

    def _target(self) -> str:
        if self.user:
            return f"{self.user}@{self.host}"
        return self.host

    def _materialize_key(self) -> None:
        """Write ``self.private_key`` contents to a temp file once."""
        if not self.private_key or self._local_key_path:
            return
        fd, path = tempfile.mkstemp(prefix="dsh-ssh-key-", suffix=".pem")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(self.private_key)
            os.chmod(path, 0o600)
        except Exception:
            os.unlink(path)
            raise
        self._local_key_path = path

    def _materialize_password(self) -> None:
        """Write the MCP child's password to a mode-600 temp file once."""
        if self.auth_type != "password" or not self.password or self._local_password_path:
            return
        fd, path = tempfile.mkstemp(prefix="dsh-ssh-pass-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(self.password)
                fh.write("\n")
            os.chmod(path, 0o600)
        except Exception:
            os.unlink(path)
            raise
        self._local_password_path = path

    async def _exec(
        self,
        remote_cmd: str,
        *,
        timeout: float | None = None,
        cwd: str | None = None,
    ) -> _ExecResult:
        """Run ``bash -lc <remote_cmd>`` on the remote host.

        The remote working directory defaults to ``remote_workdir``
        unless ``cwd`` is given (relative to ``remote_workdir``).
        Callee is responsible for quoting into ``remote_cmd``.
        """
        if cwd:
            resolved = cwd if cwd.startswith("/") else posixpath.join(self.remote_workdir, cwd)
            command = f"cd {shlex.quote(resolved)} && {remote_cmd}"
        else:
            command = f"cd {shlex.quote(self.remote_workdir)} && {remote_cmd}"
        def _run() -> _ExecResult:
            try:
                proc = self._run_remote_sync(
                    ["bash", "-lc", command],
                    timeout=timeout if timeout is not None else 600,
                )
                return _ExecResult(
                    exit_code=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                )
            except subprocess.TimeoutExpired:
                return _ExecResult(exit_code=-1, stdout=b"", stderr=b"timed out")

        if timeout is None:
            return await asyncio.to_thread(_run)
        try:
            return await asyncio.wait_for(asyncio.to_thread(_run), timeout=timeout)
        except asyncio.TimeoutError:
            return _ExecResult(exit_code=-1, stdout=b"", stderr=b"timed out")

    async def _connect_test(self) -> bool:
        """Run a trivial remote command; False when unreachable."""

        def _run() -> bool:
            try:
                proc = self._run_remote_sync(
                    ["echo", "dsh-ssh-ok"],
                    timeout=45,
                )
                return proc.returncode == 0 and b"dsh-ssh-ok" in proc.stdout
            except Exception:  # noqa: BLE001
                return False

        return await asyncio.to_thread(_run)

    async def _read(self, path: str) -> bytes:
        """Fetch a remote file as raw bytes via base64 over stdin.

        ``python3`` is used on the remote side to base64-encode the
        file so the bytes cross the ssh channel verbatim (no termios/CRLF
        rewriting) regardless of content.
        """
        abs_path = path if path.startswith("/") else posixpath.join(self.remote_workdir, path)
        py = (
            "import base64,sys;"
            f"p={abs_path!r};"
            "try:\n"
            " f=open(p,'rb').read();\n"
            " sys.stdout.write(base64.b64encode(f).decode())\n"
            "except FileNotFoundError:\n"
            " sys.stdout.write('__DOSH_ERR__')\n"
            " sys.exit(3)\n"
            "except Exception as e:\n"
            " sys.stdout.write('__DOSH_ERR__'+type(e).__name__); sys.exit(4)\n"
        )

        def _run() -> _ExecResult:
            try:
                proc = self._run_remote_sync(
                    ["python3", "-c", py],
                    timeout=120,
                )
                return _ExecResult(proc.returncode, proc.stdout, proc.stderr)
            except subprocess.TimeoutExpired:
                return _ExecResult(-1, b"", b"timed out")

        res = await asyncio.to_thread(_run)
        out = res.stdout.strip()
        if res.exit_code == 3 or out.startswith(b"__DOSH_ERR__"):
            raise FileNotFoundError(path)
        if res.exit_code != 0:
            raise OSError(f"remote read failed: {res.stderr.decode(errors='replace')}")
        return base64.b64decode(out)

    async def _write(self, path: str, content: bytes) -> None:
        """Write raw bytes to a remote file via a python3 stdin sink."""
        abs_path = path if path.startswith("/") else posixpath.join(self.remote_workdir, path)
        dirname = posixpath.dirname(abs_path)
        py = (
            "import base64,sys,os;\n"
            f"p={abs_path!r};\n"
            "os.makedirs(os.path.dirname(p), exist_ok=True);\n"
            "open(p,'wb').write(base64.b64decode(sys.stdin.read()))\n"
        )
        b64 = base64.b64encode(content).decode()

        def _run() -> _ExecResult:
            # ensure remote parent dir first
            self._run_remote_sync(
                ["bash", "-lc", f"mkdir -p {shlex.quote(dirname)}"],
                timeout=120,
            )
            try:
                proc = self._run_remote_sync(
                    ["python3", "-c", py],
                    input_data=b64.encode("utf-8"),
                    timeout=120,
                )
                return _ExecResult(proc.returncode, proc.stdout, proc.stderr)
            except subprocess.TimeoutExpired:
                return _ExecResult(-1, b"", b"timed out")

        res = await asyncio.to_thread(_run)
        if res.exit_code != 0:
            raise OSError(
                f"remote write failed: {res.stderr.decode(errors='replace')}"
            )

    # ── lifecycle ───────────────────────────────────────────────

    async def initialize(self) -> None:
        """Probe reachability, prepare ``remote_workdir``, seed MCPs/skills.

        Uses the same restoration semantics as the container policy: a
        remote ``.mcp`` file (if present) takes precedence over
        ``default_mcps``; otherwise ``default_mcps`` is adopted and
        persisted the first time it changes.
        """
        if self.is_alive:
            return

        # Restore / seed MCPs up front (needed by the sandbox bridge).
        self._mcps = await self._restore_or_seed_mcps()

        if self.auth_type == "key" and self.private_key:
            self._materialize_key()

        if not await self._connect_test():
            raise RuntimeError(
                f"SshWorkspace: cannot reach {self._target()}:{self.port} "
                f"over ssh (auth_type={self.auth_type})"
            )

        # Prepare the remote sandbox layout.
        mkdir_res = await self._exec(
            "mkdir -p "
            f"{shlex.quote(self.remote_workdir)}/{_REMOTE_DATA_DIR} "
            f"{shlex.quote(self.remote_workdir)}/{_REMOTE_SKILLS_DIR} "
            f"{shlex.quote(self.remote_workdir)}/{_REMOTE_SESSIONS_DIR} "
            f"{shlex.quote(self.remote_workdir)}"
        )
        if mkdir_res.exit_code != 0:
            raise RuntimeError(
                "SshWorkspace: failed to prepare remote workdir: "
                + mkdir_res.stderr.decode(errors="replace")
            )

        await self._seed_skills()
        self._control_active = True
        self.is_alive = True

    async def close(self) -> None:
        """Release the SSH workspace (best effort, never raises)."""
        mcps = list(self._mcps)
        self._mcps = []
        for mcp in mcps:
            close = getattr(mcp, "close", None)
            if not callable(close):
                continue
            try:
                result = close()
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "SshWorkspace: failed to close MCP %s: %s",
                    type(mcp).__name__,
                    exc,
                )
        if self._local_key_path:
            try:
                os.unlink(self._local_key_path)
            except OSError:
                pass
            self._local_key_path = None
        if self._local_password_path:
            try:
                os.unlink(self._local_password_path)
            except OSError:
                pass
            self._local_password_path = None
        self._control_active = False
        self.is_alive = False

    async def reset(self) -> None:
        """Reset the remote sandbox to an empty state (best effort)."""
        await self._exec(
            f"rm -rf {shlex.quote(self.remote_workdir)}/{_REMOTE_SESSIONS_DIR} "
            f"{shlex.quote(self.remote_workdir)}/{_REMOTE_DATA_DIR} "
            f"{shlex.quote(self.remote_workdir)}/{_REMOTE_SKILLS_DIR} && "
            f"mkdir -p {shlex.quote(self.remote_workdir)}/{_REMOTE_DATA_DIR} "
            f"{shlex.quote(self.remote_workdir)}/{_REMOTE_SKILLS_DIR} "
            f"{shlex.quote(self.remote_workdir)}/{_REMOTE_SESSIONS_DIR}"
        )

    # ── introspection ───────────────────────────────────────────

    def get_instructions(self) -> str:
        """Static workspace instructions for the model."""
        return (
            "You are working in a remote SSH sandbox. The working directory "
            f"is {self.remote_workdir}. Use the provided sandbox tools to "
            "inspect and run commands there. The directory layout contains "
            "data/, skills/ and sessions/ subfolders."
        )

    def list_tools(self) -> list[ToolBase]:
        """Remote python has no platform tools; all tools go through MCP."""
        return []

    def list_mcps(self) -> list[MCPClient]:
        return list(self._mcps)

    async def list_skills(self) -> list[Skill]:
        """List remote ``skills/`` entries (mirrors the container policy)."""
        base = posixpath.join(self.remote_workdir, _REMOTE_SKILLS_DIR)
        found = (await self._exec(f"find {shlex.quote(base)} -name SKILL.md 2>/dev/null"))
        out = (
            found.stdout.decode(errors="replace")
            if found.exit_code == 0
            else ""
        )
        skills: list[Skill] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            doc = (await self._read(line)).decode(errors="replace")
            front, body = _parse_frontmatter(doc)
            name = front.get("name")
            description = front.get("description")
            if not name or not description:
                logger.warning("SshWorkspace: skip skill missing name/description: %s", line)
                continue
            skills.append(
                Skill(
                    dir=posixpath.dirname(line),
                    markdown=doc,
                    updated_at=0.0,
                )
            )
        return skills

    async def add_skill(self, dirname: str) -> None:
        """Copy a local skill ``SKILL.md`` dir into remote ``skills/``."""
        skill_path = os.path.join(dirname, "SKILL.md")
        if not os.path.isfile(skill_path):
            raise FileNotFoundError(dirname)
        with open(skill_path, encoding="utf-8") as fh:
            content = fh.read()
        remote_dir = posixpath.join(self.remote_workdir, _REMOTE_SKILLS_DIR, os.path.basename(dirname))
        await self._write(posixpath.join(remote_dir, "SKILL.md"), content.encode("utf-8"))

    async def remove_skill(self, dirname: str) -> None:
        """Remove a remote skill directory (KeyError when missing)."""
        target = posixpath.join(self.remote_workdir, _REMOTE_SKILLS_DIR, os.path.basename(dirname))
        res = await self._exec(f"rm -rf {shlex.quote(target)} && test ! -e {shlex.quote(target)}")
        if res.exit_code != 0:
            raise KeyError(dirname)

    # ── MCP management ──────────────────────────────────────────

    async def add_mcp(self, mcp_client: MCPClient) -> None:
        """Register an MCP server and persist to remote ``.mcp``."""
        async with self._mcp_lock:
            names = {m.name for m in self._mcps}
            if mcp_client.name in names:
                raise ValueError(f"MCP server {mcp_client.name} already exists")
            self._mcps.append(mcp_client)
            await self._save_mcp_file()

    async def remove_mcp(self, name: str) -> None:
        """Remove an MCP server and persist to remote ``.mcp``."""
        async with self._mcp_lock:
            for idx, m in enumerate(self._mcps):
                if m.name == name:
                    self._mcps.pop(idx)
                    await self._save_mcp_file()
                    return
            raise ValueError(f"MCP server {name} not found")

    async def _restore_or_seed_mcps(self) -> list[MCPClient]:
        """Adopt remote ``.mcp`` when present, else ``default_mcps``."""
        try:
            data = await self._read(posixpath.join(self.remote_workdir, ".mcp"))
            parsed = json.loads(data.decode("utf-8"))
            return [MCPClient.model_validate(m) for m in parsed]
        except Exception:  # noqa: BLE001
            return list(self.default_mcps)

    async def _save_mcp_file(self) -> None:
        """Persist ``self._mcps`` to remote ``.mcp`` (best effort)."""
        try:
            payload = json.dumps(
                [m.model_dump() for m in self._mcps],
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")
            await self._write(posixpath.join(self.remote_workdir, ".mcp"), payload)
        except Exception as e:  # noqa: BLE001
            logger.warning("SshWorkspace: failed to save remote .mcp: %s", e)

    async def _seed_skills(self) -> None:
        """Seed local ``skill_paths`` into remote ``skills/`` once."""
        if not self.skill_paths:
            return
        try:
            existing = (await self._exec(f"ls -A {shlex.quote(posixpath.join(self.remote_workdir, _REMOTE_SKILLS_DIR))} 2>/dev/null"))
            if existing.stdout.strip():
                return  # already populated — respect user state
        except Exception:  # noqa: BLE001
            return
        for path in self.skill_paths:
            try:
                await self.add_skill(path)
            except Exception as e:  # noqa: BLE001
                logger.warning("SshWorkspace: skip skill %r: %s", path, e)

    # ── offload ─────────────────────────────────────────────────

    async def offload_context(self, session_id: str, msgs: list[Msg]) -> str:
        """Persist messages as JSONL under ``sessions/<id>/context.jsonl``."""
        base = posixpath.join(self.remote_workdir, _REMOTE_SESSIONS_DIR, session_id)
        path = posixpath.join(base, "context.jsonl")

        import copy as _copy

        copied = _copy.deepcopy(msgs)
        lines: list[str] = []
        for msg in copied:
            if not isinstance(msg.content, str):
                content = []
                for block in msg.content:
                    if isinstance(block, DataBlock) and isinstance(block.source, Base64Source):
                        block = await self._offload_data_block(block)
                    content.append(block)
                msg.content = content
            lines.append(msg.model_dump_json())

        await self._exec(f"mkdir -p {shlex.quote(base)}")
        existing = b""
        try:
            existing = await self._read(path)
        except (FileNotFoundError, OSError):
            pass
        await self._write(path, existing + ("\n".join(lines) + "\n").encode("utf-8"))
        return path

    async def offload_tool_result(self, session_id: str, tool_result: ToolResultBlock) -> str:
        """Persist a tool result as ``sessions/<id>/tool_result-<id>.txt``."""
        base = posixpath.join(self.remote_workdir, _REMOTE_SESSIONS_DIR, session_id)
        path = posixpath.join(base, f"tool_result-{tool_result.id}.txt")

        parts: list[str] = []
        if isinstance(tool_result.output, str):
            parts.append(tool_result.output)
        else:
            for block in tool_result.output:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
                elif isinstance(block, DataBlock):
                    if isinstance(block.source, Base64Source):
                        d = await self._offload_data_block(block)
                        url = str(d.source.url)
                    else:
                        url = str(block.source.url)
                    parts.append(
                        f"<data url='{url}' name='{block.name}' "
                        f"media_type='{block.source.media_type}'/>"
                    )

        await self._exec(f"mkdir -p {shlex.quote(base)}")
        await self._write(path, "".join(parts).encode("utf-8"))
        return path

    async def _offload_data_block(self, block: DataBlock) -> DataBlock:
        """Extract a base64 DataBlock into ``data/`` and return a file:// URL."""
        if not isinstance(block.source, Base64Source):
            return block
        digest = hashlib.sha256(block.source.data.encode("utf-8")).hexdigest()
        ext = mimetypes.guess_extension(block.source.media_type) or ".bin"
        rel = posixpath.join(self.remote_workdir, _REMOTE_DATA_DIR, f"{digest}{ext}")
        raw = base64.b64decode(block.source.data)
        await self._write(rel, raw)
        return DataBlock(
            id=block.id,
            name=block.name,
            source=URLSource(url=AnyUrl(f"file://{rel}")),
        )


def _parse_frontmatter(doc: str) -> tuple[dict[str, str], str]:
    """Very small SKILL.md frontmatter parser (YAML-ish subset)."""
    front: dict[str, str] = {}
    rest = doc
    if doc.lstrip().startswith("---"):
        body = doc.lstrip()[3:]
        end = body.find("\n---")
        if end != -1:
            chunk = body[:end]
            for line in chunk.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    front[key.strip()] = val.strip()
            rest = body[end + 4:]
    return front, rest


# ─────────────────────────────────────────────────────────────────
# SSH inline stdio FastMCP server
# ─────────────────────────────────────────────────────────────────

# The runtime should be enough to run the sandbox MCP server.  On the
# platform host the gateway uses this project's python, which already
# ships ``mcp`` (a runtime dependency of agentscope).  The script is a
# single ``str`` so it compiles and unit-tests on the host while the
# gateway spawns ``python -c <script>`` locally.
_SSH_INLINE_SERVER = """\
import json
import os
import shlex as _sh
import subprocess
import sys

from mcp.server.fastmcp import FastMCP

_HOST = os.environ.get("SSH_HOST", "")
_PORT = os.environ.get("SSH_PORT", "22")
_USER = os.environ.get("SSH_USER", "")
_AUTH_TYPE = os.environ.get("SSH_AUTH_TYPE", "password")
_PASSWORD_FILE = os.environ.get("SSH_PASSWORD_FILE", "")
_KEY_PATH = os.environ.get("SSH_KEY_PATH", "")
_ROOT = os.environ.get("SSH_REMOTE_WORKDIR", "/workspace")

mcp = FastMCP("sandbox")


def _ssh_args():
    args = [
        "ssh", "-p", str(_PORT),
        "-o", "StrictHostKeyChecking=yes",
        "-o", "ConnectTimeout=30",
        "-o", "BatchMode=yes" if _AUTH_TYPE == "key" else "BatchMode=no",
    ]
    if _AUTH_TYPE == "key" and _KEY_PATH:
        args += ["-i", _KEY_PATH]
    return args


def _target():
    if _USER:
        return f"{_USER}@{_HOST}"
    return _HOST


def _read_password():
    if not _PASSWORD_FILE:
        return ""
    try:
        with open(_PASSWORD_FILE, encoding="utf-8") as password_file:
            return password_file.read().rstrip("\\r\\n")
    except OSError:
        return ""


def _call(argv, input_text=None, timeout=600):
    cmd = list(_ssh_args()) + list(argv)
    password_read_fd = None
    password_write_fd = None
    process = None
    try:
        if _AUTH_TYPE == "password":
            password = _read_password()
            if not password:
                return None
            password_read_fd, password_write_fd = os.pipe()
            cmd = ["sshpass", "-d", str(password_read_fd)] + cmd
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            pass_fds=(password_read_fd,) if password_read_fd is not None else (),
        )
        if password_write_fd is not None:
            with os.fdopen(password_write_fd, "w", encoding="utf-8") as password_stream:
                password_stream.write(password)
                password_stream.flush()
            password_write_fd = None
        if password_read_fd is not None:
            os.close(password_read_fd)
            password_read_fd = None
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
        return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
            stdout, stderr = process.communicate()
            return subprocess.CompletedProcess(cmd, -1, stdout, stderr)
        return None
    except FileNotFoundError:
        return None
    finally:
        for fd in (password_read_fd, password_write_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass


def _remote_python_command(source, *args):
    command = "python3 -c " + _sh.quote(source)
    if args:
        command += " -- " + " ".join(_sh.quote(str(arg)) for arg in args)
    return command


def _abspath(path):
    p = os.path.abspath(os.path.join(_ROOT, os.path.expanduser(path)))
    if not p.startswith(_ROOT):
        raise ValueError("path escapes workspace: " + path)
    return p


@mcp.tool()
def bash(command: str, cwd: str = ".") -> str:
    \"\"\"Run a shell command inside the remote sandbox.

    Args:
        command: The shell command line to execute.
        cwd: Relative directory (under the remote workdir) to run in.
    \"\"\"
    workdir = _ROOT if cwd in ("", ".") else _abspath(cwd)
    import shlex as _sh
    remote = f"cd {_sh.quote(workdir)} && {command}"
    proc = _call([_target(), "bash", "-lc", remote])
    if proc is None:
        return json.dumps({"ok": False, "error": "ssh unavailable or timed out"})
    return json.dumps({
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-100000:],
        "stderr": proc.stderr[-100000:],
    })


@mcp.tool()
def read(path: str, offset: int = 0, limit: int = 2000) -> str:
    \"\"\"Read a text file inside the remote sandbox.

    Args:
        path: File path (relative to the remote workdir).
        offset: Zero-based starting line.
        limit: Max number of lines to return.
    \"\"\"
    try:
        p = _abspath(path)
    except ValueError as e:
        return json.dumps({"ok": False, "error": str(e)})
    py = (
        "import json,sys\\n"
        "p=sys.argv[1]\\n"
        "try:\\n"
        " f=open(p,'r',encoding='utf-8',errors='replace')\\n"
        " lines=f.readlines(); f.close()\\n"
        "except FileNotFoundError:\\n"
        " sys.stdout.write('__DOSH_NOFILE__'); sys.exit(0)\\n"
        "except Exception as e:\\n"
        " sys.stdout.write('__DOSH_ERR__'+repr(e)); sys.exit(0)\\n"
        "sys.stdout.write(json.dumps({'lines': lines}))\\n"
    )
    proc = _call(
        [_target(), "bash", "-lc", _remote_python_command(py, p)],
        timeout=120,
    )
    if proc is None:
        return json.dumps({"ok": False, "error": "ssh unavailable or timed out"})
    out = proc.stdout.strip()
    if out == "__DOSH_NOFILE__":
        return json.dumps({"ok": False, "error": "no such file: " + path})
    if out.startswith("__DOSH_ERR__"):
        return json.dumps({"ok": False, "error": out.split("__DOSH_ERR__", 1)[1]})
    try:
        data = json.loads(out)
        lines = data.get("lines", [])
    except Exception:
        lines = []
    chunk = lines[offset: offset + limit]
    return json.dumps({
        "ok": True,
        "content": "".join(chunk),
        "total_lines": len(lines),
        "start_line": offset,
    })


@mcp.tool()
def write(path: str, content: str) -> str:
    \"\"\"Create or overwrite a text file inside the remote sandbox.

    Args:
        path: File path (relative to the remote workdir).
        content: Full file content to write.
    \"\"\"
    try:
        p = _abspath(path)
    except ValueError as e:
        return json.dumps({"ok": False, "error": str(e)})
    py = (
        "import os,sys\\n"
        "p=sys.argv[1]\\n"
        "data=sys.stdin.read()\\n"
        "os.makedirs(os.path.dirname(p),exist_ok=True)\\n"
        "open(p,'w',encoding='utf-8').write(data)\\n"
        "print('ok')\\n"
    )
    proc = _call(
        [_target(), "bash", "-lc", _remote_python_command(py, p)],
        input_text=content,
        timeout=120,
    )
    if proc is None:
        return json.dumps({"ok": False, "error": "ssh unavailable or timed out"})
    if proc.returncode != 0:
        return json.dumps({"ok": False, "error": proc.stderr.strip()[-100000:]})
    return json.dumps({"ok": True, "path": path})


@mcp.tool()
def glob(pattern: str, cwd: str = ".") -> str:
    \"\"\"List files under the remote workdir matching a glob pattern.

    Args:
        pattern: Glob pattern (relative to the remote workdir).
        cwd: Subdirectory to search in.
    \"\"\"
    try:
        base = _ROOT if cwd in ("", ".") else _abspath(cwd)
    except ValueError as e:
        return json.dumps({"ok": False, "error": str(e)})
    py = (
        "import glob,json,sys\\n"
        "pattern=sys.argv[1]\\n"
        "base=sys.argv[2]\\n"
        "try:\\n"
        " matches=glob.glob(pattern,root_dir=base,recursive=True)\\n"
        " print(json.dumps({'files':sorted(matches)[:500]}))\\n"
        "except Exception as e:\\n"
        " print('__DOSH_ERR__'+repr(e)); sys.exit(0)\\n"
    )
    proc = _call(
        [_target(), "bash", "-lc", _remote_python_command(py, pattern, base)],
        timeout=120,
    )
    if proc is None:
        return json.dumps({"ok": False, "error": "ssh unavailable or timed out"})
    out = proc.stdout.strip()
    if out.startswith("__DOSH_ERR__"):
        return json.dumps({"ok": False, "error": out.split("__DOSH_ERR__", 1)[1]})
    try:
        data = json.loads(out)
        files = data.get("files", [])
    except Exception:
        files = []
    return json.dumps({"ok": True, "files": files})


mcp.run(transport="stdio")
"""


def build_ssh_tool_mcp(
    *,
    host: str,
    port: int = 22,
    user: str = "",
    auth_type: str = "password",
    password_file_path: str | None = None,
    private_key_path: str | None = None,
    remote_workdir: str = SSH_REMOTE_WORKDIR,
) -> MCPClient:
    """Return the stateful STDIO MCP handshake for SSH-forwarded tools.

    The gateway spawns ``python -c <script>`` **locally** (on the
    platform host).  The script reaches the remote sandbox through its
    own ``ssh`` child process, so connection parameters must be
    injected through ``env`` — including the materialized private key
    file path (created by :class:`SshWorkspace` and cleaned up on
    :meth:`SshWorkspace.close`). Passwords use the same mode-600 file
    mechanism; the cleartext secret is never placed in the MCP child's
    argv or environment.
    """
    normalized_auth_type = (auth_type or "password").lower()
    env: dict[str, str] = {
        "SSH_HOST": host,
        "SSH_PORT": str(port),
        "SSH_USER": user or "",
        "SSH_AUTH_TYPE": normalized_auth_type,
        "SSH_REMOTE_WORKDIR": remote_workdir or SSH_REMOTE_WORKDIR,
    }
    if normalized_auth_type == "password":
        if not password_file_path:
            raise ValueError("password SSH MCP requires password_file_path")
        env["SSH_PASSWORD_FILE"] = password_file_path
    elif normalized_auth_type == "key" and private_key_path:
        env["SSH_KEY_PATH"] = private_key_path

    return MCPClient(
        name=SSH_MCP_NAME,
        is_stateful=True,
        mcp_config=StdioMCPConfig(
            command=sys.executable,
            args=["-c", _SSH_INLINE_SERVER],
            cwd=os.getcwd(),
            env=env,
        ),
    )
