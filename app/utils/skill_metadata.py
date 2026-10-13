"""SKILL.md Frontmatter 解析与技能附件隐式指令构建。"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

USER_MESSAGE_CONTEXT_DIVIDER = "\n\n---\n\n"


def parse_skill_frontmatter(skill_id: str, skill_md_path: str) -> Dict[str, str]:
    """从 SKILL.md 顶部 YAML Frontmatter 提取 name / description 等元数据。"""
    meta: Dict[str, str] = {"id": skill_id, "name": skill_id, "description": "", "enabled": "true"}
    if not os.path.exists(skill_md_path):
        return meta
    try:
        with open(skill_md_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(8192)
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if match:
            for line in match.group(1).splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip().lower()] = value.strip().strip('"').strip("'")
    except Exception:
        pass
    if "enabled" not in meta:
        meta["enabled"] = "true"
    return meta


def toggle_skill_enabled_in_file(skill_md_path: str, enabled: bool) -> bool:
    """在 SKILL.md 的 YAML Frontmatter 中修改或插入 enabled 状态。"""
    if not os.path.exists(skill_md_path):
        return False
    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if match:
            yaml_block = match.group(1)
            rest_content = content[match.end():]
            
            new_lines = []
            has_enabled = False
            for line in yaml_block.splitlines():
                if line.strip().lower().startswith("enabled:"):
                    new_lines.append(f"enabled: {str(enabled).lower()}")
                    has_enabled = True
                else:
                    new_lines.append(line)
            
            if not has_enabled:
                new_lines.append(f"enabled: {str(enabled).lower()}")
                
            new_yaml_block = "\n".join(new_lines)
            new_content = f"---\n{new_yaml_block}\n---\n{rest_content}"
            
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True
    except Exception:
        pass
    return False


def format_skill_meta_text(meta: Dict[str, str]) -> str:
    """将 Frontmatter 格式化为隐式指令中的 meta 摘要。"""
    name = (meta.get("name") or meta.get("id") or "").strip()
    desc = (meta.get("description") or "").strip()
    parts: List[str] = []
    if name:
        parts.append(f"name: {name}")
    if desc:
        parts.append(f"description: {desc}")
    return ", ".join(parts) if parts else "（无 SKILL.md Frontmatter 元数据）"


def build_skill_attachment_hint(
    skill_id: str,
    *,
    skill_name: Optional[str] = None,
    meta_override: Optional[Dict[str, Any]] = None,
) -> str:
    """构建技能挂载隐式指令（含路径与 Frontmatter meta）。"""
    from app.core.config import settings

    skill_md_path = os.path.join(settings.SKILLS_DIR, skill_id, "SKILL.md")
    if meta_override:
        meta = {
            "id": skill_id,
            "name": str(meta_override.get("name") or skill_id),
            "description": str(meta_override.get("description") or ""),
        }
    else:
        meta = parse_skill_frontmatter(skill_id, skill_md_path)

    display_name = (skill_name or meta.get("name") or skill_id).replace(" (技能)", "")
    path = f"/app/data/skills/{skill_id}/SKILL.md"
    meta_text = format_skill_meta_text(meta)
    return (
        f"用户本轮已调用生态技能工作流：{display_name}，对应的物理描述文件绝对路径是：{path}。\n"
        f"skills meta 为：{meta_text}"
    )


def enrich_messages_with_skill_meta(messages: List[Dict[str, Any]]) -> None:
    """若最后一条 user 消息挂载技能但隐式指令缺少 meta，则补全或重建技能上下文块。"""
    if not messages:
        return
    last = messages[-1]
    files = last.get("files") or []
    skill_files = [f for f in files if f.get("type") == "skill"]
    if not skill_files:
        return
    content = last.get("content") or ""
    if "skills meta 为：" in content:
        return

    hints = []
    for sf in skill_files:
        skill_id = sf.get("url")
        if not skill_id:
            continue
        skill_name = (sf.get("filename") or "").replace(" (技能)", "")
        meta_override = sf.get("skillMeta") or sf.get("skill_meta")
        hints.append(
            build_skill_attachment_hint(
                skill_id,
                skill_name=skill_name,
                meta_override=meta_override,
            )
        )
    if not hints:
        return

    context_block = "\n\n".join(hints)
    if USER_MESSAGE_CONTEXT_DIVIDER in content:
        user_part, _ctx = content.split(USER_MESSAGE_CONTEXT_DIVIDER, 1)
        user_part = user_part.strip()
        if user_part:
            last["content"] = f"{user_part}{USER_MESSAGE_CONTEXT_DIVIDER}{context_block}"
        else:
            last["content"] = f"{USER_MESSAGE_CONTEXT_DIVIDER}{context_block}"
    elif content.strip():
        last["content"] = f"{content.strip()}{USER_MESSAGE_CONTEXT_DIVIDER}{context_block}"
    else:
        last["content"] = f"{USER_MESSAGE_CONTEXT_DIVIDER}{context_block}"


# 隐式指令里的技能正文路径：前端 getServerAttachmentPath 与本模块 build_skill_attachment_hint
# 都写死成这一种形状（"/app/data/skills/<技能 id>/SKILL.md"），因此按它识别"这条提示指向哪个技能"。
SKILL_MD_ABSOLUTE_PATH_RE = re.compile(r"/app/data/skills/([^/\s]+)/SKILL\.md")

# 上下文块内部各条附件提示之间的分隔（前端 contextLines.join("\n\n") 与本模块 hints 拼接同源）
_CONTEXT_HINT_SEPARATOR = "\n\n"

FORBIDDEN_SKILL_ATTACHMENT_NOTICE = (
    "用户本轮挂载的技能「{skill_id}」已被管理员禁用，不可使用；"
    "其技能描述文件不可读取，禁止尝试读取或检索该技能的任何文件。"
)


def forbidden_skill_attachment_notice(skill_id: str) -> str:
    """被禁技能的挂载说明：明确"不可用、不可读"，且**不带任何绝对路径**。"""
    return FORBIDDEN_SKILL_ATTACHMENT_NOTICE.format(skill_id=str(skill_id or "").strip())


def _skill_attachment_id(item: Any) -> str:
    if not isinstance(item, dict) or item.get("type") != "skill":
        return ""
    return str(item.get("url") or "").strip()


def _skill_attachment_is_personal(item: Any) -> bool:
    """挂载项是否指向**个人技能**（个人技能与公共技能可能同名）。"""
    if not isinstance(item, dict):
        return False
    scopes = [item.get("scope")]
    meta = item.get("skillMeta") or item.get("skill_meta")
    if isinstance(meta, dict):
        scopes.append(meta.get("scope"))
    return any(str(scope or "").strip().lower() == "personal" for scope in scopes)


def _rewrite_forbidden_skill_hints(content: str, blocked_ids: set[str]) -> str:
    if not blocked_ids:
        return content
    parts = content.split(_CONTEXT_HINT_SEPARATOR)
    rewritten: list[str] = []
    changed = False
    for part in parts:
        hit_ids = {
            skill_id
            for skill_id in SKILL_MD_ABSOLUTE_PATH_RE.findall(part)
            if skill_id in blocked_ids
        }
        if not hit_ids:
            rewritten.append(part)
            continue
        changed = True
        rewritten.append(
            "\n".join(forbidden_skill_attachment_notice(skill_id) for skill_id in sorted(hit_ids))
        )
    if not changed:
        return content
    return _CONTEXT_HINT_SEPARATOR.join(rewritten)


def sanitize_forbidden_skill_context(
    messages: List[Dict[str, Any]],
    forbidden_ids: Optional[Any],
) -> int:
    """就地清洗被禁技能的挂载项与提示文本，返回被移除的附件个数。

    必须在 ``memory_service.add_message``（落库）与 ``enrich_messages_with_skill_meta``
    （依据 files 重建提示）**之前**调用：挂载提示里带着被禁技能 SKILL.md 的绝对路径，
    等于在提示词里教模型去读被禁技能的正文；落库之后这条路径还会永久留在会话历史里。

    两条处理，缺一不可：
    1. ``files`` 里被禁技能附件直接移除（模型看不到"已挂载"这件事）；
    2. 已生成的提示文本整条改写成明确的不可用说明——只删附件不改文本的话，历史里
       旧提示拼接出来的绝对路径仍然会进模型。

    个人技能（scope=personal）不受影响：产品口径是"禁的是平台发布的那一份"，
    用户自建的同名技能照旧可用，因此同名 id 先按 scope 排除再算禁用集合。
    """
    forbidden = {
        str(skill_id).strip()
        for skill_id in (forbidden_ids or ())
        if str(skill_id).strip()
    }
    if not forbidden or not messages:
        return 0

    removed = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        files = message.get("files")
        skill_items = (
            [item for item in files if isinstance(item, dict) and item.get("type") == "skill"]
            if isinstance(files, list)
            else []
        )
        personal_ids = {
            _skill_attachment_id(item)
            for item in skill_items
            if _skill_attachment_is_personal(item)
        }
        blocked_ids = forbidden - personal_ids
        if not blocked_ids:
            continue

        if isinstance(files, list):
            kept = [
                item
                for item in files
                if not (
                    isinstance(item, dict)
                    and item.get("type") == "skill"
                    and _skill_attachment_id(item) in blocked_ids
                )
            ]
            if len(kept) != len(files):
                removed += len(files) - len(kept)
                message["files"] = kept

        content = message.get("content")
        if isinstance(content, str) and content:
            rewritten = _rewrite_forbidden_skill_hints(content, blocked_ids)
            if rewritten != content:
                message["content"] = rewritten
    return removed
