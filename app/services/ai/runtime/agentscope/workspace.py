from __future__ import annotations

import hashlib
import inspect
import json
import logging
import os
import re
import shutil
import uuid
from dataclasses import replace
from typing import Any

from app.services.ai.tools.registry import AGENTSCOPE_BUILTIN_TOOL_ALIASES

logger = logging.getLogger(__name__)

WORKSPACE_BUILTIN_TOOL_NAMES = frozenset(
    {"Bash", "Read", "Write", "Edit", "Glob", "Grep"}
)
WORKSPACE_PROMPT_TOOL_NAMES = WORKSPACE_BUILTIN_TOOL_NAMES
WORKSPACE_REPLACED_PLATFORM_TOOL_NAMES = frozenset(
    {
        *WORKSPACE_BUILTIN_TOOL_NAMES,
        *AGENTSCOPE_BUILTIN_TOOL_ALIASES.keys(),
        "list_available_skills",
        "read_skill_instruction",
    }
)

_workspace_cache: dict[str, Any] = {}


WORKSPACE_USER_KEY_SEP = "__"
USER_DOCS_DIR_NAME = "docs"
USER_SESSIONS_DIR_NAME = "sessions"


def _clean_key_part(value: str | None, fallback_prefix: str) -> str:
    raw = value or f"{fallback_prefix}_{uuid.uuid4().hex[:12]}"
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    return cleaned or f"{fallback_prefix}_{uuid.uuid4().hex[:12]}"


def extract_workspace_identity(
    *,
    user_id: str | int | None = None,
    user_name: str | None = None,
    user_info: dict[str, Any] | None = None,
) -> tuple[str | int | None, str | None]:
    """Resolve workspace identity from explicit args or user_info."""
    resolved_user_id = user_id
    resolved_user_name = user_name
    if user_info:
        if resolved_user_id is None:
            resolved_user_id = user_info.get("user_id") or user_info.get("id")
        if not resolved_user_name:
            raw_name = user_info.get("user_name") or user_info.get("username")
            resolved_user_name = str(raw_name).strip() if raw_name else None
    if resolved_user_name:
        resolved_user_name = str(resolved_user_name).strip() or None
    return resolved_user_id, resolved_user_name


def resolve_workspace_user_key(
    *,
    user_id: str | int | None,
    user_name: str | None = None,
) -> str:
    """Build a readable, stable workspace directory key: user_name__user_id."""
    if user_id is None:
        return _clean_key_part(None, "anonymous")

    uid_str = str(user_id).strip()
    if not uid_str:
        return _clean_key_part(None, "anonymous")

    raw_name = (user_name or "").strip()
    if raw_name:
        name_part = _clean_key_part(raw_name, "user")
        id_part = _clean_key_part(uid_str, "user")
        return f"{name_part}{WORKSPACE_USER_KEY_SEP}{id_part}"

    return _clean_key_part(uid_str, "anonymous")


def build_workspace_key(trace_id: str | None, conversation_id: str | None = None) -> str:
    trace_part = _clean_key_part(trace_id, "trace")
    if not conversation_id:
        return trace_part
    return f"{trace_part}__{_clean_key_part(conversation_id, 'conversation')}"


def default_workspace_root() -> str:
    for candidate in ("/app/data/agent_workspaces", "data/agent_workspaces"):
        if candidate == "/app/data/agent_workspaces" and not os.path.exists("/app/data"):
            continue
        return os.path.abspath(candidate)
    return os.path.abspath("data/agent_workspaces")


def discover_platform_skill_paths(
    user_info: dict[str, Any] | None = None,
    *,
    skills_custom: bool = False,
    allowed_global_skills: list[str] | None = None,
) -> list[str]:
    """Collect skill directories: global platform skills + user personal skills.

    When skills_custom is True, only allowlisted global skill ids are included;
    personal skills are always appended (if enabled).
    """
    try:
        from app.core.config import settings

        skills_root = getattr(settings, "SKILLS_DIR", None)
    except Exception:
        return []
    if not skills_root or not os.path.isdir(skills_root):
        return []

    allowlist: set[str] | None = None
    if skills_custom:
        allowlist = {str(s).strip() for s in (allowed_global_skills or []) if str(s).strip()}

    paths: list[str] = []
    from app.utils.skill_metadata import parse_skill_frontmatter
    for entry in sorted(os.listdir(skills_root)):
        skill_dir = os.path.join(skills_root, entry)
        if os.path.isdir(skill_dir) and os.path.isfile(os.path.join(skill_dir, "SKILL.md")):
            if allowlist is not None and entry not in allowlist:
                continue
            # 过滤禁用的技能
            meta = parse_skill_frontmatter(entry, os.path.join(skill_dir, "SKILL.md"))
            if meta.get("enabled", "true") == "false":
                continue
            paths.append(os.path.abspath(skill_dir))

    # 追加用户个人技能路径
    if user_info:
        try:
            from app.services.ai.skill_resolver import get_user_personal_skills_dir

            personal_dir = get_user_personal_skills_dir(user_info)
            if personal_dir and os.path.isdir(personal_dir):
                for entry in sorted(os.listdir(personal_dir)):
                    skill_dir = os.path.join(personal_dir, entry)
                    if os.path.isdir(skill_dir) and os.path.isfile(
                        os.path.join(skill_dir, "SKILL.md")
                    ):
                        meta = parse_skill_frontmatter(entry, os.path.join(skill_dir, "SKILL.md"))
                        if meta.get("enabled", "true") == "false":
                            continue
                        abs_path = os.path.abspath(skill_dir)
                        if abs_path not in paths:
                            paths.append(abs_path)
        except Exception as exc:
            logger.debug("[workspace] Failed to load personal skill paths: %s", exc)

    return paths


async def resolve_workspace_root(*, ensure_exists: bool = True) -> str:
    try:
        from app.services.config_service import ConfigService

        raw = await ConfigService.get("agentscope_workspace_root")
        if raw:
            return os.path.abspath(str(raw))
    except Exception as exc:
        logger.warning("[workspace] Failed to load agentscope_workspace_root: %s", exc)
    root = default_workspace_root()
    if ensure_exists:
        os.makedirs(root, exist_ok=True)
    return root


def resolve_user_sessions_dir(
    *,
    root: str,
    user_id: str | int | None,
    user_name: str | None = None,
    user_info: dict[str, Any] | None = None,
) -> str:
    """用户级会话目录容器：agent_workspaces/{user_key}/sessions。"""
    resolved_user_id, resolved_user_name = extract_workspace_identity(
        user_id=user_id,
        user_name=user_name,
        user_info=user_info,
    )
    uid = resolve_workspace_user_key(
        user_id=resolved_user_id,
        user_name=resolved_user_name,
    )
    return os.path.join(os.path.abspath(root), uid, USER_SESSIONS_DIR_NAME)


def resolve_legacy_session_workdir(
    *,
    root: str,
    user_id: str | int | None,
    conversation_id: str,
    user_name: str | None = None,
    user_info: dict[str, Any] | None = None,
) -> str:
    """旧版会话目录：agent_workspaces/{user_key}/{conversation_id}（兼容历史数据）。"""
    resolved_user_id, resolved_user_name = extract_workspace_identity(
        user_id=user_id,
        user_name=user_name,
        user_info=user_info,
    )
    uid = resolve_workspace_user_key(
        user_id=resolved_user_id,
        user_name=resolved_user_name,
    )
    cid = _clean_key_part(conversation_id, "conversation")
    return os.path.join(os.path.abspath(root), uid, cid)


def resolve_session_workdir(
    *,
    root: str,
    user_id: str | int | None,
    conversation_id: str,
    user_name: str | None = None,
    user_info: dict[str, Any] | None = None,
) -> str:
    resolved_user_id, resolved_user_name = extract_workspace_identity(
        user_id=user_id,
        user_name=user_name,
        user_info=user_info,
    )
    uid = resolve_workspace_user_key(
        user_id=resolved_user_id,
        user_name=resolved_user_name,
    )
    cid = _clean_key_part(conversation_id, "conversation")
    return os.path.join(os.path.abspath(root), uid, USER_SESSIONS_DIR_NAME, cid)


def resolve_user_docs_dir(
    *,
    root: str,
    user_id: str | int | None,
    user_name: str | None = None,
    user_info: dict[str, Any] | None = None,
) -> str:
    """用户级文档目录：agent_workspaces/{user_key}/docs（跨会话集中存放 AI 落盘文件）。"""
    resolved_user_id, resolved_user_name = extract_workspace_identity(
        user_id=user_id,
        user_name=user_name,
        user_info=user_info,
    )
    uid = resolve_workspace_user_key(
        user_id=resolved_user_id,
        user_name=resolved_user_name,
    )
    return os.path.join(os.path.abspath(root), uid, USER_DOCS_DIR_NAME)


def resolve_user_workspace_root(
    *,
    root: str,
    user_id: str | int | None,
    user_name: str | None = None,
    user_info: dict[str, Any] | None = None,
) -> str | None:
    """Return the per-user workspace root when it exists on disk."""
    resolved_user_id, resolved_user_name = extract_workspace_identity(
        user_id=user_id,
        user_name=user_name,
        user_info=user_info,
    )
    user_key = resolve_workspace_user_key(
        user_id=resolved_user_id,
        user_name=resolved_user_name,
    )
    user_root = os.path.normpath(os.path.join(os.path.abspath(root), user_key))
    if os.path.isdir(user_root):
        return user_root
    return None


def _sanitize_skill_dir_name(name: str) -> str:
    """Replicate AgentScope's ``_sanitize_dir_name`` for pre-seeded layout.

    Allowed characters: ASCII letters/digits/underscore (``\\w``), CJK
    unified ideographs (一-鿿), and hyphens. Everything else becomes ``_``.
    Must stay byte-for-byte identical to the third-party implementation so
    the pre-seeded directory names match what AgentScope would produce.
    """
    return re.sub(r"[^\w一-鿿-]", "_", name)


def _hardlink_or_copy2(src: str, dst: str) -> None:
    """copytree ``copy_function``: hard-link first, copy2 on cross-device.

    Pre-seeding session ``skills/`` uses hard links so 400+ sessions share a
    single physical copy of every skill file instead of duplicating disk.
    When the source and destination live on different filesystems (e.g.
    Docker multi-volume mounts), ``os.link`` raises ``EXDEV``; fall back to
    a normal ``shutil.copy2`` so seeding always succeeds. ``copy2`` also
    copies metadata (mtime), keeping the snapshot faithful.
    """
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _preseed_session_skills(workdir: str, skill_paths: list[str]) -> None:
    """Pre-seed ``<workdir>/skills`` with the platform skills before AgentScope.

    AgentScope's ``LocalWorkspace.initialize`` seeds ``skill_paths`` into
    ``<workdir>/skills`` via ``shutil.copytree`` (a full physical copy per
    session), which multiplies disk usage linearly as sessions accumulate.
    This function pre-populates the same directory using hard links toward
    the shared source skill dirs (or ``copy2`` on cross-device) and writes an
    AgentScope-compatible ``.skills`` index, so that when ``initialize`` runs
    it finds every skill's content hash already present and skips all copying
    — eliminating the per-session duplication while keeping full COW-like
    isolation where the filesystem supports hard links.

    Idempotent: if ``<workdir>/skills/.skills`` already exists the seed is
    left untouched, so re-initialisation never rebuilds or overwrites a
    snapshot.

    Hard-link caveat (honest limitation): linked files share the same inode
    as the source. AgentScope never writes into session ``skills/`` and the
    platform's ``create_skills`` writes to the user/global source dirs, so a
    session snapshot stays effectively read-only; however if a source skill
    file were later modified in place, already-linked session copies would
    observe that change. Cross-device mounts fall back to real copies (no
    sharing), which is safe but re-introduces per-session duplication.
    """
    skills_dir = os.path.join(workdir, "skills")
    index_path = os.path.join(skills_dir, ".skills")
    if os.path.isfile(index_path):
        return

    os.makedirs(skills_dir, exist_ok=True)

    # Load any existing index so we never clobber previously seeded skills.
    existing: dict[str, dict[str, str]] = {}
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        stored = data.get("skills")
        if isinstance(stored, dict):
            existing = {
                str(d): {"hash": str(e.get("hash", "")), "skill_name": str(e.get("skill_name", ""))}
                for d, e in stored.items()
                if isinstance(e, dict)
            }
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("[workspace] Failed to parse existing .skills: %s", exc)

    existing_hashes: set[str] = {e.get("hash", "") for e in existing.values()}
    existing_agent_names: set[str] = {e.get("skill_name", "") for e in existing.values()}
    existing_dir_names: set[str] = set(existing.keys())

    # Parse SKILL.md frontmatter the same way AgentScope's frontmatter.loads
    # does, so `name` and the content hash match exactly.
    try:
        import frontmatter
    except Exception:
        frontmatter = None

    updated = False
    for skill_path in skill_paths:
        skill_md_path = os.path.join(skill_path, "SKILL.md")
        try:
            with open(skill_md_path, "rb") as fh:
                raw = fh.read()
            content_str = raw.decode("utf-8")
        except Exception as exc:
            logger.warning("[workspace] Pre-seed skip unreadable skill %s: %s", skill_path, exc)
            continue

        # parse name/description
        name: str | None = None
        if frontmatter is not None:
            try:
                parsed = frontmatter.loads(content_str)
                name = str(parsed.get("name") or "") or None
                description = str(parsed.get("description") or "") or None
            except Exception:
                name = None
                description = None
        else:
            # Fallback: minimal line-based frontmatter parse for name only.
            description = None
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content_str, re.DOTALL)
            if match:
                for line in match.group(1).splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        if key.strip().lower() == "name":
                            name = value.strip().strip('"').strip("'")
        if not name or not description:
            logger.warning(
                "[workspace] Pre-seed skip %s: SKILL.md missing name/description",
                skill_path,
            )
            continue

        skill_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
        if skill_hash in existing_hashes:
            continue

        # Resolve agent-facing name conflict (mirror AgentScope loop)
        agent_name = name
        counter = 1
        while agent_name in existing_agent_names:
            agent_name = f"{name} ({counter})"
            counter += 1

        # Resolve directory name conflict (mirror AgentScope loop)
        base_dir = _sanitize_skill_dir_name(name)
        dir_name = base_dir
        counter = 1
        while dir_name in existing_dir_names:
            dir_name = f"{base_dir}_{counter}"
            counter += 1

        dest_path = os.path.join(skills_dir, dir_name)
        if not os.path.realpath(dest_path).startswith(
            os.path.realpath(skills_dir) + os.sep,
        ):
            logger.warning("[workspace] Pre-seed skip %s: path escapes skills_dir", skill_path)
            continue

        try:
            shutil.copytree(
                skill_path,
                dest_path,
                copy_function=_hardlink_or_copy2,
                dirs_exist_ok=False,
            )
        except Exception as exc:
            logger.warning("[workspace] Pre-seed failed to copy skill %s: %s", skill_path, exc)
            continue

        existing[dir_name] = {"hash": skill_hash, "skill_name": agent_name}
        existing_hashes.add(skill_hash)
        existing_agent_names.add(agent_name)
        existing_dir_names.add(dir_name)
        updated = True

    if updated:
        try:
            mtime = os.stat(skills_dir).st_mtime
        except OSError:
            mtime = 0.0
        payload = {"skills_dir_mtime": float(mtime), "skills": existing}
        try:
            with open(index_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, indent=2, ensure_ascii=False))
            logger.info(
                "[workspace] Pre-seeded %d skill(s) via hard links in %s",
                updated,
                skills_dir,
            )
        except Exception as exc:
            logger.warning("[workspace] Failed to write .skills at %s: %s", skills_dir, exc)


async def get_local_workspace(
    *,
    user_id: str | int | None,
    conversation_id: str | None,
    user_name: str | None = None,
    user_info: dict[str, Any] | None = None,
    skills_custom: bool = False,
    allowed_global_skills: list[str] | None = None,
) -> Any | None:
    """Return an initialized LocalWorkspace for the conversation."""
    if not conversation_id:
        return None

    root = await resolve_workspace_root()
    workdir = resolve_session_workdir(
        root=root,
        user_id=user_id,
        user_name=user_name,
        user_info=user_info,
        conversation_id=conversation_id,
    )
    os.makedirs(workdir, exist_ok=True)
    skill_paths = discover_platform_skill_paths(
        user_info=user_info,
        skills_custom=skills_custom,
        allowed_global_skills=allowed_global_skills,
    )
    skills_fp = (
        f"custom:{','.join(sorted(str(s) for s in (allowed_global_skills or []) if str(s).strip()))}"
        if skills_custom
        else "all"
    )
    cache_key = f"{workdir}::{skills_fp}"
    cached = _workspace_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from agentscope.workspace import LocalWorkspace
    except Exception as exc:
        logger.warning("[workspace] LocalWorkspace unavailable: %s", exc)
        return None

    workspace = LocalWorkspace(
        workdir=workdir,
        skill_paths=skill_paths,
    )
    try:
        # Pre-seed session skills/ with hard links + matching .skills index so
        # AgentScope's initialize() hash-skips all copies instead of duplicating
        # every skill into each session directory.
        _preseed_session_skills(workdir, skill_paths)
        await workspace.initialize()
    except Exception as exc:
        logger.warning("[workspace] Failed to initialize LocalWorkspace workdir=%s: %s", workdir, exc)
        return None

    _workspace_cache[cache_key] = workspace
    return workspace


async def get_local_workspace_offloader(
    *,
    user_id: str | int | None,
    conversation_id: str | None,
    user_name: str | None = None,
    user_info: dict[str, Any] | None = None,
    skills_custom: bool = False,
    allowed_global_skills: list[str] | None = None,
) -> Any | None:
    """Backward-compatible alias for get_local_workspace."""
    return await get_local_workspace(
        user_id=user_id,
        conversation_id=conversation_id,
        user_name=user_name,
        user_info=user_info,
        skills_custom=skills_custom,
        allowed_global_skills=allowed_global_skills,
    )


async def delete_workspace_for_session(
    user_id: str | int | None,
    conversation_id: str | None,
    user_name: str | None = None,
    user_info: dict[str, Any] | None = None,
) -> None:
    if not conversation_id:
        return
    root = await resolve_workspace_root()
    workdir = resolve_session_workdir(
        root=root,
        user_id=user_id,
        user_name=user_name,
        user_info=user_info,
        conversation_id=conversation_id,
    )
    _workspace_cache.pop(workdir, None)
    prefix = f"{workdir}::"
    for key in list(_workspace_cache.keys()):
        if key == workdir or (isinstance(key, str) and key.startswith(prefix)):
            _workspace_cache.pop(key, None)
    if not os.path.isdir(workdir):
        return
    try:
        shutil.rmtree(workdir)
    except Exception as exc:
        logger.warning("[workspace] Failed to delete workdir=%s: %s", workdir, exc)


def clear_workspace_cache() -> None:
    _workspace_cache.clear()


def normalize_workspace_tool_names(tool_names: set[str] | frozenset[str]) -> set[str]:
    aliases = {
        "exec_command": "Bash",
        "read_file": "Read",
        "write_file": "Write",
        "search_text": "Grep",
        "edit_file": "Edit",
        "glob_files": "Glob",
    }
    normalized: set[str] = set()
    for name in tool_names:
        canonical = aliases.get(name, name)
        normalized.add(canonical)
    return normalized


def collect_workspace_file_tool_names(tools: list[Any]) -> set[str]:
    names: set[str] = set()
    for tool in tools or []:
        tool_name = getattr(tool, "name", None)
        if tool_name:
            names.add(str(tool_name))
    return normalize_workspace_tool_names(names) & WORKSPACE_PROMPT_TOOL_NAMES


async def append_session_workspace_sandbox_to_system_prompt(
    system_content: str,
    *,
    user_id: str | int | None,
    conversation_id: str | None,
    tools: list[Any],
    user_name: str | None = None,
    user_info: dict[str, Any] | None = None,
) -> str:
    """Append session workspace + path sandbox guidance when file/shell tools are bound."""
    file_tools = collect_workspace_file_tool_names(tools)
    if not conversation_id or not file_tools:
        return system_content

    if "[Session Workspace & Path Sandbox]" in (system_content or ""):
        return system_content

    from app.services.ai.agent_prompts import AgentServicePrompts

    root = await resolve_workspace_root()
    session_workdir = resolve_session_workdir(
        root=root,
        user_id=user_id,
        user_name=user_name,
        user_info=user_info,
        conversation_id=conversation_id,
    )
    docs_dir = resolve_user_docs_dir(
        root=root,
        user_id=user_id,
        user_name=user_name,
        user_info=user_info,
    )
    block = AgentServicePrompts.session_workspace_sandbox_block(
        session_workdir=session_workdir,
        docs_dir=docs_dir,
        file_tool_names=sorted(file_tools),
    )
    base = (system_content or "").strip()
    if base:
        return f"{base}\n\n{block}"
    return block


def _workspace_native_name_for_spec(spec: Any) -> str | None:
    native_tool = getattr(spec, "native_tool", None)
    native_name = getattr(native_tool, "name", None) if native_tool is not None else None
    if native_name in WORKSPACE_BUILTIN_TOOL_NAMES:
        return str(native_name)
    spec_name = str(getattr(spec, "name", "") or "")
    aliased = AGENTSCOPE_BUILTIN_TOOL_ALIASES.get(spec_name, spec_name)
    if aliased in WORKSPACE_BUILTIN_TOOL_NAMES:
        return aliased
    return None


async def bind_configured_tools_to_workspace(
    workspace: Any,
    tool_specs: list[Any] | None,
) -> list[Any]:
    """Bind configured Bash/Read/Write/Edit/Glob/Grep to the session workspace.

    Replaces already-configured native tools with LocalWorkspace copies so Bash
    starts in ``workspace.workdir``. Does not inject extra builtins the agent
    did not configure. Returns the original list when workspace is missing.
    """
    specs = list(tool_specs or [])
    if workspace is None or not specs:
        return specs

    list_tools = getattr(workspace, "list_tools", None)
    if list_tools is None:
        return specs

    try:
        listed = list_tools()
        if inspect.isawaitable(listed):
            listed = await listed
    except Exception as exc:
        logger.warning("[workspace] Failed to list workspace tools: %s", exc)
        return specs

    if not isinstance(listed, (list, tuple)):
        return specs

    workspace_tools = {
        str(getattr(tool, "name", "") or ""): tool
        for tool in (listed or [])
        if getattr(tool, "name", None)
    }
    if not workspace_tools:
        return specs

    from app.services.ai.runtime.agentscope.tools import (
        runtime_tool_spec_from_native_agentscope_tool,
    )

    bound: list[Any] = []
    for spec in specs:
        native_name = _workspace_native_name_for_spec(spec)
        workspace_tool = workspace_tools.get(native_name or "")
        if workspace_tool is None:
            bound.append(spec)
            continue
        if native_name == "Bash":
            try:
                from app.services.ai.runtime.conversation_run_subprocess import (
                    attach_cancellable_backend,
                )

                attach_cancellable_backend(workspace_tool)
            except Exception:
                pass
        rebound = runtime_tool_spec_from_native_agentscope_tool(
            workspace_tool,
            source_type=getattr(spec, "source_type", "system"),
            permission_scope=getattr(spec, "permission_scope", None),
        )
        bound.append(
            replace(
                rebound,
                description=spec.description or rebound.description,
                evidence_types=getattr(spec, "evidence_types", rebound.evidence_types),
                evidence_policy=getattr(spec, "evidence_policy", rebound.evidence_policy),
                evidence_inference_disabled=bool(
                    getattr(spec, "evidence_inference_disabled", False)
                ),
                timeout_seconds=getattr(spec, "timeout_seconds", None),
                audit_callback=getattr(spec, "audit_callback", None),
            )
        )
    return bound


def is_workspace_managed_tool_spec(spec: Any) -> bool:
    """Tools replaced by LocalWorkspace builtins or AgentScope skill viewer."""
    name = getattr(spec, "name", "")
    if name in WORKSPACE_REPLACED_PLATFORM_TOOL_NAMES:
        return True
    native_tool = getattr(spec, "native_tool", None)
    native_name = getattr(native_tool, "name", None) if native_tool is not None else None
    return native_name in WORKSPACE_BUILTIN_TOOL_NAMES


async def build_workspace_toolkit(
    workspace: Any,
    tool_specs: list[Any],
    *,
    approval_mode: str | None = None,
):
    """显式合并 LocalWorkspace 内置文件工具与平台工具（Runner 默认不再调用）。

    AgentScope LocalWorkspace 会通过 list_tools() 返回 Bash/Read/Write/Edit/Glob/Grep。
    平台 Runner 现已改为只挂载 agent 配置工具；如需 workspace 内置工具，请在 agent
    后端配置对应别名（如 grep、read_file、exec_command）。
    """
    from app.services.ai.runtime.agentscope.tools import (
        _load_agentscope_toolkit,
        runtime_tool_from_native,
        runtime_tool_from_spec,
    )

    toolkit_cls = _load_agentscope_toolkit()
    workspace_tools = await workspace.list_tools()
    workspace_names = {getattr(tool, "name", "") for tool in workspace_tools}
    if workspace_names != set(WORKSPACE_BUILTIN_TOOL_NAMES):
        logger.warning(
            "[workspace] Unexpected workspace tools: %s",
            sorted(workspace_names),
        )

    runtime_workspace_tools = [
        runtime_tool_from_native(tool, approval_mode=approval_mode)
        for tool in workspace_tools
    ]
    platform_tools = [
        runtime_tool_from_spec(
            spec,
            approval_mode=approval_mode,
        )
        for spec in tool_specs
        if not is_workspace_managed_tool_spec(spec)
    ]
    skills = await workspace.list_skills()
    mcps = await workspace.list_mcps()
    return toolkit_cls(
        tools=[*runtime_workspace_tools, *platform_tools],
        skills_or_loaders=skills,
        mcps=mcps,
    )
