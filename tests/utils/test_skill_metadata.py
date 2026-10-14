import pytest

from app.utils.skill_metadata import (
    build_skill_attachment_hint,
    enrich_messages_with_skill_meta,
    format_skill_meta_text,
    parse_skill_frontmatter,
    upgrade_legacy_skill_mount_hints,
)

pytestmark = pytest.mark.no_infrastructure


def test_parse_skill_frontmatter(tmp_path):
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        '---\nname: 演示技能\ndescription: "用于测试的技能说明"\n---\n# Body\n',
        encoding="utf-8",
    )
    meta = parse_skill_frontmatter("demo-skill", str(skill_dir / "SKILL.md"))
    assert meta["name"] == "演示技能"
    assert meta["description"] == "用于测试的技能说明"


def test_format_skill_meta_text():
    text = format_skill_meta_text({"name": "foo", "description": "bar"})
    assert text == "name: foo, description: bar"


def test_build_skill_attachment_hint_with_override():
    hint = build_skill_attachment_hint(
        "my-skill",
        skill_name="展示名",
        meta_override={"name": "my-skill", "description": "技能描述"},
    )
    assert "展示名" in hint
    assert "技能 ID：my-skill" in hint
    assert "已随本轮上下文预载" in hint
    # 关键回归：提示里不能再出现任何文件系统路径。曾经写死的
    # /app/data/skills/<id>/SKILL.md 对个人技能与 Docker/K8s 沙箱都不成立。
    assert "/app/data/skills" not in hint
    assert "skills meta 为：name: my-skill, description: 技能描述" in hint


def test_build_skill_attachment_hint_prefers_explicit_skill_dir():
    """调用方确知技能真实目录时给目录；否则退回 list_accessible_directories 指引。"""
    hint = build_skill_attachment_hint(
        "p1",
        meta_override={"name": "个人技能"},
        skill_dir="/app/data/agent_workspaces/admin__1/skills/p1",
    )
    assert "/app/data/agent_workspaces/admin__1/skills/p1" in hint
    assert "list_accessible_directories" not in hint

    fallback = build_skill_attachment_hint("p1", meta_override={"name": "个人技能"})
    assert "list_accessible_directories" in fallback
    assert "/app/data/agent_workspaces" not in fallback


def test_enrich_messages_with_skill_meta(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "auto-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: 自动技能\ndescription: 从磁盘读取\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.core.config.settings",
        type("S", (), {"SKILLS_DIR": str(skills_dir)})(),
    )

    messages = [
        {
            "role": "user",
            "content": (
                "\n\n---\n\n"
                "用户本轮已调用生态技能工作流：自动技能（技能 ID：auto-skill）。"
                "其 SKILL.md 正文已随本轮上下文预载，本轮直接按预载指令执行，无需再读取技能文件。"
            ),
            "files": [{"type": "skill", "url": "auto-skill", "filename": "自动技能 (技能)"}],
        }
    ]
    enrich_messages_with_skill_meta(messages)
    assert "skills meta 为：name: 自动技能, description: 从磁盘读取" in messages[0]["content"]
    assert "/app/data/skills" not in messages[0]["content"]
    assert "技能 ID：auto-skill" in messages[0]["content"]


LEGACY_MOUNT_HINT = (
    "用户本轮已调用生态技能工作流：Alpha，对应的物理描述文件绝对路径是："
    "/app/data/skills/alpha/SKILL.md。\nskills meta 为：name: Alpha, description: 演示"
)


def test_upgrade_legacy_skill_mount_hints_rewrites_dead_path():
    """老会话里的死路径提示就地升级：换掉那半句，技能名 / meta 行 / 用户正文都不动。"""
    messages = [
        {"role": "user", "content": "帮我看看\n\n---\n\n" + LEGACY_MOUNT_HINT},
        {"role": "assistant", "content": "好的"},
    ]

    assert upgrade_legacy_skill_mount_hints(messages) == 1

    content = messages[0]["content"]
    assert "/app/data/skills" not in content
    assert "Alpha（技能 ID：alpha）" in content, "显示名要保留，并换成 ID 标记"
    assert "已随本轮上下文预载" in content
    assert "list_accessible_directories" in content
    assert "skills meta 为：name: Alpha, description: 演示" in content, "meta 行必须原样保留"
    assert "帮我看看" in content
    assert messages[1]["content"] == "好的", "不含旧提示的消息逐字节不动"


def test_upgrade_legacy_skill_mount_hints_is_a_noop_for_new_format():
    """新格式里没有可升级的东西：不能重复改写，也不能碰用户正文。"""
    content = "问题\n\n---\n\n" + build_skill_attachment_hint(
        "alpha", meta_override={"name": "Alpha"}
    )
    messages = [{"role": "user", "content": content}]

    assert upgrade_legacy_skill_mount_hints(messages) == 0
    assert messages[0]["content"] == content


def test_upgrade_legacy_skill_mount_hints_leaves_user_text_alone():
    """只有「挂载提示说明行」才升级：用户自己提到这条路径时不能被改写。"""
    messages = [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "见 /app/data/skills/alpha/SKILL.md 这份文档"},
        "not-a-dict",
        {"role": "user", "content": "提问：/app/data/skills/alpha/SKILL.md 这个路径是什么"},
    ]

    assert upgrade_legacy_skill_mount_hints(messages) == 0
    assert messages[1]["content"] == "见 /app/data/skills/alpha/SKILL.md 这份文档"
    assert messages[3]["content"] == "提问：/app/data/skills/alpha/SKILL.md 这个路径是什么"
    assert upgrade_legacy_skill_mount_hints([]) == 0
