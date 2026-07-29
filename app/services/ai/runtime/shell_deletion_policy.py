from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from typing import Iterable, Literal


DeletionAction = Literal["pass", "ask", "deny"]


@dataclass(frozen=True)
class ShellDeletionDecision:
    action: DeletionAction
    reason: str = ""
    targets: tuple[str, ...] = ()


_CONTROL_TOKENS = set(";&|()<>")
_DELETE_COMMANDS = {"rm", "rmdir", "unlink", "shred"}
_SHELL_WRAPPERS = {"command", "exec", "busybox"}
_SUDO_OPTIONS_WITH_VALUE = {
    "-u",
    "--user",
    "-g",
    "--group",
    "-C",
    "--chdir",
    "-R",
    "--role",
    "-t",
    "--type",
}
_SHELL_INTERPRETERS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
_PROGRAMMATIC_DELETE_MARKERS = re.compile(
    r"\b(?:os\.(?:remove|unlink)|shutil\.rmtree|(?:fs\.)?(?:rm|rmSync|rmdir|rmdirSync|unlink|unlinkSync)|rmtree|unlink|remove)\b",
    re.IGNORECASE,
)
_DYNAMIC_SHELL_MARKERS = re.compile(
    r"\$\(|`|<\(|\b(?:for|while|until|if|case|function)\b",
    re.IGNORECASE,
)
_DELETE_INTENT_MARKERS = re.compile(
    r"\b(?:rm|rmdir|unlink|shred|find|delete|git\s+clean)\b",
    re.IGNORECASE,
)

_PROTECTED_SYSTEM_ROOTS = (
    "/",
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/home",
    "/lib",
    "/lib64",
    "/media",
    "/mnt",
    "/opt",
    "/proc",
    "/root",
    "/run",
    "/sbin",
    "/srv",
    "/sys",
    "/tmp",
    "/usr",
    "/var",
    "/app",
    "/app/data",
    "/app/data/skills",
    # macOS global roots, in addition to the Unix roots above.
    "/Applications",
    "/Library",
    "/Network",
    "/System",
    "/Users",
    "/Volumes",
    "/private",
    "/cores",
)


def assess_shell_deletion(
    command: str,
    *,
    cwd: str | os.PathLike[str] | None = None,
    protected_roots: Iterable[str] = (),
) -> ShellDeletionDecision:
    """Classify shell deletion operations without executing the command.

    Protected roots and full-content wildcard operations are hard denied.
    Other deletion operations require an explicit permission confirmation.
    Commands that cannot be statically analyzed are never auto-allowed.
    """
    current_dir = _canonical_path(os.fspath(cwd) if cwd is not None else os.getcwd())
    roots = _build_protected_roots(current_dir, protected_roots)
    return _assess_command(command or "", current_dir=current_dir, roots=roots, depth=0)


def _assess_command(
    command: str,
    *,
    current_dir: str,
    roots: set[str],
    depth: int,
) -> ShellDeletionDecision:
    if not command.strip():
        return ShellDeletionDecision("pass")

    if depth > 2:
        return ShellDeletionDecision(
            "ask",
            "删除命令嵌套层级无法安全解析，需要确认",
        )

    try:
        tokens = _shell_tokens(command)
    except ValueError:
        if _DELETE_INTENT_MARKERS.search(command):
            return ShellDeletionDecision(
                "ask",
                "删除命令解析失败，需要确认",
            )
        return ShellDeletionDecision("pass")

    if _has_dynamic_shell(command) and _DELETE_INTENT_MARKERS.search(command):
        return ShellDeletionDecision(
            "ask",
            "删除命令包含无法静态解析的 Shell 结构，需要确认",
        )

    decisions: list[ShellDeletionDecision] = []
    for segment in _split_shell_segments(tokens):
        decision = _assess_segment(
            segment,
            command=command,
            current_dir=current_dir,
            roots=roots,
            depth=depth,
        )
        if decision.action == "deny":
            return decision
        if decision.action == "ask":
            decisions.append(decision)

    if decisions:
        targets = tuple(target for decision in decisions for target in decision.targets)
        reasons = tuple(dict.fromkeys(decision.reason for decision in decisions if decision.reason))
        return ShellDeletionDecision(
            "ask",
            "; ".join(reasons) or "删除操作需要确认",
            targets,
        )
    return ShellDeletionDecision("pass")


def _assess_segment(
    tokens: list[str],
    *,
    command: str,
    current_dir: str,
    roots: set[str],
    depth: int,
) -> ShellDeletionDecision:
    if not tokens:
        return ShellDeletionDecision("pass")

    base_index = _find_base_command(tokens)
    if base_index is None:
        if _PROGRAMMATIC_DELETE_MARKERS.search(command):
            return ShellDeletionDecision(
                "ask",
                "命令可能执行程序化删除，需要确认",
            )
        return ShellDeletionDecision("pass")

    base = _command_basename(tokens[base_index])
    rest = tokens[base_index + 1 :]

    if base in _SHELL_INTERPRETERS:
        nested = _shell_payload_after_c(rest)
        if nested is None:
            return ShellDeletionDecision("pass")
        return _assess_command(
            nested,
            current_dir=current_dir,
            roots=roots,
            depth=depth + 1,
        )

    if base == "eval":
        return _assess_command(
            " ".join(rest),
            current_dir=current_dir,
            roots=roots,
            depth=depth + 1,
        )

    if base in _DELETE_COMMANDS:
        targets = _delete_targets(rest)
        if not targets:
            return ShellDeletionDecision(
                "ask",
                "删除命令未能解析目标，需要确认",
            )
        return _classify_targets(targets, current_dir=current_dir, roots=roots)

    if base == "find" and "-delete" in rest:
        targets = tuple(
            token
            for token in rest
            if not token.startswith("-") and token not in {"{}", ";"}
        )
        if not targets:
            return ShellDeletionDecision(
                "ask",
                "find 删除范围未能解析，需要确认",
            )
        return _classify_targets(targets, current_dir=current_dir, roots=roots)

    if base == "git" and len(rest) > 0 and rest[0] == "clean":
        return ShellDeletionDecision(
            "ask",
            "git clean 会删除工作区内容，需要确认",
        )

    if base in {"python", "python3", "perl", "node", "ruby"}:
        return _assess_programmatic_delete(
            " ".join(rest),
            current_dir=current_dir,
            roots=roots,
        )

    return ShellDeletionDecision("pass")


def _build_protected_roots(
    current_dir: str,
    extra_roots: Iterable[str],
) -> set[str]:
    roots = {_canonical_path(path) for path in _PROTECTED_SYSTEM_ROOTS}
    roots.add(current_dir)
    roots.add(_canonical_path(os.path.expanduser("~")))
    roots.add(_canonical_path(os.path.join(current_dir, "data", "agent_workspaces")))
    roots.add(_canonical_path(os.path.expanduser("~/.agents/skills")))

    for path in extra_roots:
        if path:
            roots.add(_canonical_path(os.fspath(path), base=current_dir))

    try:
        from app.core.config import settings

        skills_dir = getattr(settings, "SKILLS_DIR", None)
        if skills_dir:
            roots.add(_canonical_path(os.fspath(skills_dir), base=current_dir))
    except Exception:
        pass

    return roots


def _classify_targets(
    targets: tuple[str, ...],
    *,
    current_dir: str,
    roots: set[str],
) -> ShellDeletionDecision:
    for target in targets:
        if _is_protected_target(target, current_dir=current_dir, roots=roots):
            return ShellDeletionDecision(
                "deny",
                f"禁止删除受保护的系统或工作区目录: {target}",
                targets,
            )
    return ShellDeletionDecision(
        "ask",
        f"删除操作需要用户确认: {', '.join(targets)}",
        targets,
    )


def _is_protected_target(
    target: str,
    *,
    current_dir: str,
    roots: set[str],
) -> bool:
    raw_target = target.strip().strip("'\"")
    if not raw_target:
        return True

    if raw_target in {"~", "$HOME", "${HOME}"}:
        return True

    wildcard_root = _wildcard_base(raw_target)
    if wildcard_root is not None:
        if wildcard_root in {"*", "**", ".", "./"}:
            return current_dir in roots
        normalized = _resolve_path(wildcard_root, current_dir=current_dir)
        return normalized in roots

    if any(marker in raw_target for marker in ("$", "`", "(", ")")):
        return False

    normalized = _resolve_path(raw_target, current_dir=current_dir)
    return normalized in roots


def _wildcard_base(target: str) -> str | None:
    if target in {"*", "**", "./*", "./**"}:
        return "."
    for suffix in ("/**", "/*"):
        if target.endswith(suffix):
            return target[: -len(suffix)] or "/"
    return None


def _delete_targets(tokens: list[str]) -> tuple[str, ...]:
    targets: list[str] = []
    after_separator = False
    for token in tokens:
        if token == "--":
            after_separator = True
            continue
        if not after_separator and token.startswith("-") and token != "-":
            continue
        if token in _CONTROL_TOKENS:
            continue
        targets.append(token)
    return tuple(targets)


def _find_base_command(tokens: list[str]) -> int | None:
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if _is_assignment(token):
            index += 1
            continue

        base = _command_basename(token)
        if base in {"sudo", "doas"}:
            index = _skip_sudo_options(tokens, index + 1)
            continue
        if base == "env":
            index += 1
            while index < len(tokens):
                candidate = tokens[index]
                if candidate.startswith("-") or _is_assignment(candidate):
                    index += 1
                    continue
                break
            continue
        if base in _SHELL_WRAPPERS:
            if index + 1 < len(tokens) and tokens[index + 1] == "--":
                index += 2
                continue
            index += 1
            continue
        return index
    return None


def _skip_sudo_options(tokens: list[str], index: int) -> int:
    while index < len(tokens):
        token = tokens[index]
        if token in _SUDO_OPTIONS_WITH_VALUE:
            index += 2
        elif token.startswith("-"):
            index += 1
        else:
            break
    return index


def _shell_payload_after_c(tokens: list[str]) -> str | None:
    for index, token in enumerate(tokens):
        if token == "-c" and index + 1 < len(tokens):
            return " ".join(tokens[index + 1 :])
    return None


def _shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    return list(lexer)


def _split_shell_segments(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token and all(char in _CONTROL_TOKENS for char in token):
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def _resolve_path(path: str, *, current_dir: str) -> str:
    expanded = path
    if path in {"~", "$HOME", "${HOME}"}:
        expanded = os.path.expanduser("~")
    elif path.startswith("~"):
        expanded = os.path.expanduser(path)
    elif path.startswith("$"):
        return ""
    if not os.path.isabs(expanded):
        expanded = os.path.join(current_dir, expanded)
    return _canonical_path(expanded)


def _canonical_path(path: str, *, base: str | None = None) -> str:
    value = os.fspath(path)
    if not os.path.isabs(value):
        value = os.path.join(base or os.getcwd(), value)
    return os.path.realpath(os.path.abspath(value))


def _command_basename(token: str) -> str:
    return os.path.basename(token).lower()


def _is_assignment(token: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token))


def _has_dynamic_shell(command: str) -> bool:
    return bool(_DYNAMIC_SHELL_MARKERS.search(command))


def _assess_programmatic_delete(
    text: str,
    *,
    current_dir: str,
    roots: set[str],
) -> ShellDeletionDecision:
    if not (
        _PROGRAMMATIC_DELETE_MARKERS.search(text)
        or _DELETE_INTENT_MARKERS.search(text)
    ):
        return ShellDeletionDecision("pass")

    asks: list[ShellDeletionDecision] = []
    for literal in _quoted_literals(text):
        if not _looks_like_path_literal(literal):
            continue
        decision = _classify_targets((literal,), current_dir=current_dir, roots=roots)
        if decision.action == "deny":
            return decision
        asks.append(decision)

    for literal in _quoted_literals(text):
        if _DELETE_INTENT_MARKERS.search(literal):
            decision = _assess_command(
                literal,
                current_dir=current_dir,
                roots=roots,
                depth=1,
            )
            if decision.action == "deny":
                return decision
            if decision.action == "ask":
                asks.append(decision)

    if asks:
        return ShellDeletionDecision(
            "ask",
            "命令可能执行程序化删除，需要确认",
            tuple(target for decision in asks for target in decision.targets),
        )
    return ShellDeletionDecision("ask", "命令可能执行程序化删除，需要确认")


def _quoted_literals(text: str) -> tuple[str, ...]:
    return tuple(match.group(2) for match in re.finditer(r"(['\"])(.*?)\1", text))


def _looks_like_path_literal(value: str) -> bool:
    return value in {"~", "$HOME", "${HOME}"} or value.startswith(("/", "./", "../", "~"))
