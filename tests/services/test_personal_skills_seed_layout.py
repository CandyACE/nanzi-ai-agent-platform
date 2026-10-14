"""个人技能源历史遗留 ``.seed`` 布局的回归测试。

背景：K8s 沙箱在补齐技能子挂载之前只挂载了整个用户工作区，AgentScope 的技能根
``${workdir}/skills`` 恰好就是个人技能源目录，它 ``initialize()`` 时的布局迁移把平铺技能
**搬移**进了 ``<user>/skills/.seed/<skill_id>/``。而平台所有主机侧枚举都会跳过点开头目录
（``skill_resolver._scan_skill_dir``、portal ``list_personal_skills``、工作台计数……），
于是技能在「技能列表 / 个人技能中心 / 工作台」里集体隐形，表现为 `list_available_skills`
返回 ``[]``。

这里锁住两条不变式：
1. 平铺与 ``.seed`` 两种布局都能读到（平铺优先，同名冲突时以平铺为准）；
2. 编辑类操作会定位到技能**真实所在**目录，而不是在平铺位置新建副本。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# ── 工具函数 ─────────────────────────────────────────────────────────────


def _write_skill(root: Path, skill_id: str, *, seed: bool = False, body: str = "") -> Path:
    """在 ``root/<id>`` 或 ``root/.seed/<id>`` 下造一个最小可用技能。"""
    base = root / ".seed" if seed else root
    skill_dir = base / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_id}\ndescription: {skill_id} 描述\n---\n\n# {skill_id}\n{body}",
        encoding="utf-8",
    )
    return skill_dir


def _load_repair_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "repair_personal_skills_layout.py"
    )
    spec = importlib.util.spec_from_file_location("repair_personal_skills_layout", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ── 1. 目录枚举 helper ───────────────────────────────────────────────────


def test_iter_personal_skill_dirs_reads_flat_and_seed(tmp_path):
    from app.services.ai.skill_resolver import iter_personal_skill_dirs

    root = tmp_path / "skills"
    flat = _write_skill(root, "flat-skill")
    seeded = _write_skill(root, "seed-skill", seed=True)

    found = dict(iter_personal_skill_dirs(str(root)))

    assert set(found) == {"flat-skill", "seed-skill"}
    assert Path(found["flat-skill"]) == flat
    assert Path(found["seed-skill"]) == seeded


def test_iter_personal_skill_dirs_prefers_flat_on_conflict(tmp_path):
    from app.services.ai.skill_resolver import iter_personal_skill_dirs

    root = tmp_path / "skills"
    flat = _write_skill(root, "dup", body="flat")
    _write_skill(root, "dup", seed=True, body="seeded")

    found = dict(iter_personal_skill_dirs(str(root)))

    assert Path(found["dup"]) == flat, "同名时必须以规范平铺布局为准"


def test_iter_personal_skill_dirs_ignores_non_skill_entries(tmp_path):
    from app.services.ai.skill_resolver import iter_personal_skill_dirs

    root = tmp_path / "skills"
    _write_skill(root, "real-skill")
    (root / ".seed" / "no-skill-md").mkdir(parents=True)  # 缺 SKILL.md
    (root / "not-a-dir.txt").write_text("x", encoding="utf-8")
    (root / ".hidden").mkdir()

    # 判定口径与 _scan_skill_dir 一致：只看「目录 + 合法 id」，缺 SKILL.md 的实现
    # 会交给 parse_skill_frontmatter 兜底，因此这里仍会列出
    assert [name for name, _ in iter_personal_skill_dirs(str(root))] == [
        "no-skill-md",
        "real-skill",
    ]


def test_resolve_personal_skill_dir_falls_back_to_seed(tmp_path):
    from app.services.ai.skill_resolver import resolve_personal_skill_dir

    root = tmp_path / "skills"
    seeded = _write_skill(root, "seed-skill", seed=True)
    flat = _write_skill(root, "flat-skill")

    assert Path(resolve_personal_skill_dir(str(root), "seed-skill")) == seeded
    assert Path(resolve_personal_skill_dir(str(root), "flat-skill")) == flat
    assert resolve_personal_skill_dir(str(root), "missing-skill") is None


# ── 2. 技能列表（list_available_skills 的数据源）────────────────────────


def test_list_skill_metas_reads_seeded_personal_skill(tmp_path, monkeypatch):
    from app.services.ai import skill_resolver

    personal_root = tmp_path / "u1" / "skills"
    _write_skill(personal_root, "seed-skill", seed=True)
    monkeypatch.setattr(
        skill_resolver,
        "get_user_personal_skills_dir",
        lambda user_info=None: str(personal_root),
    )
    skill_resolver.clear_skill_meta_cache()

    metas = skill_resolver.list_skill_metas(user_info={"user_id": "u1"})

    personal = [m for m in metas if m.get("scope") == "personal"]
    assert [m["id"] for m in personal] == ["seed-skill"]
    assert personal[0]["skill_md_path"].endswith(".seed/seed-skill/SKILL.md")


def test_list_skill_metas_personal_merges_flat_and_seed(tmp_path, monkeypatch):
    from app.services.ai import skill_resolver

    personal_root = tmp_path / "u1" / "skills"
    _write_skill(personal_root, "flat-skill")
    _write_skill(personal_root, "seed-skill", seed=True)
    monkeypatch.setattr(
        skill_resolver,
        "get_user_personal_skills_dir",
        lambda user_info=None: str(personal_root),
    )
    skill_resolver.clear_skill_meta_cache()

    metas = skill_resolver.list_skill_metas(user_info={"user_id": "u1"})
    personal_ids = {m["id"] for m in metas if m.get("scope") == "personal"}

    assert personal_ids == {"flat-skill", "seed-skill"}


def test_public_skill_root_does_not_scan_seed(tmp_path, monkeypatch):
    """公共技能库是平台维护的规范布局，不接受 ``.seed``（避免误把沙箱副本当技能）。"""
    from app.services.ai import skill_resolver

    public_root = tmp_path / "public"
    public_root.mkdir()
    _write_skill(public_root, "seeded-in-public", seed=True)

    # allow_seed 默认为 False：公共技能根不认 .seed
    assert skill_resolver._scan_skill_dir(str(public_root), "global") == []


# ── 3. 个人技能中心（编辑类操作必须命中真实目录）─────────────────────────


def test_validate_personal_skill_path_resolves_seeded_skill(tmp_path, monkeypatch):
    from app.api.portal.endpoints import personal_skills

    personal_root = tmp_path / "u1" / "skills"
    seeded = _write_skill(personal_root, "seed-skill", seed=True)
    monkeypatch.setattr(
        personal_skills, "_get_personal_skills_root", lambda user_info: str(personal_root)
    )

    resolved = personal_skills._validate_personal_skill_path({"user_id": "u1"}, "seed-skill")

    assert Path(resolved) == seeded, "必须指向 .seed 里的真实目录，否则编辑会新建副本"


def test_validate_personal_skill_path_uses_flat_for_new_skill(tmp_path, monkeypatch):
    from app.api.portal.endpoints import personal_skills

    personal_root = tmp_path / "u1" / "skills"
    personal_root.mkdir(parents=True)
    monkeypatch.setattr(
        personal_skills, "_get_personal_skills_root", lambda user_info: str(personal_root)
    )

    resolved = personal_skills._validate_personal_skill_path({"user_id": "u1"}, "brand-new")

    assert Path(resolved) == personal_root / "brand-new"


# ── 4. 工作台个人技能计数 ────────────────────────────────────────────────


def test_count_personal_skills_counts_seeded_skill(tmp_path, monkeypatch):
    from app.services import workbench_home_service
    from app.services.ai import skill_resolver

    personal_root = tmp_path / "u1" / "skills"
    _write_skill(personal_root, "seed-skill", seed=True)
    monkeypatch.setattr(
        skill_resolver,
        "get_user_personal_skills_dir",
        lambda user_info=None: str(personal_root),
    )

    assert workbench_home_service._count_personal_skills({"user_id": "u1"}) == 1


# ── 5. 存量迁移脚本 ──────────────────────────────────────────────────────


def test_repair_layout_dry_run_then_apply(tmp_path, capsys):
    module = _load_repair_module()
    workspaces = tmp_path / "agent_workspaces"
    personal_root = workspaces / "u1" / "skills"
    _write_skill(personal_root, "seed-skill", seed=True)

    assert module.main(["--root", str(workspaces)]) == 0
    assert (personal_root / ".seed" / "seed-skill").is_dir(), "dry-run 不得改动文件"

    assert module.main(["--root", str(workspaces), "--apply"]) == 0
    capsys.readouterr()
    assert (personal_root / "seed-skill" / "SKILL.md").is_file()
    assert not (personal_root / ".seed").exists(), "搬空后的 .seed 应被清理"


def test_repair_layout_never_overwrites_conflict(tmp_path):
    module = _load_repair_module()
    workspaces = tmp_path / "agent_workspaces"
    personal_root = workspaces / "u1" / "skills"
    _write_skill(personal_root, "dup", body="flat-original")
    _write_skill(personal_root, "dup", seed=True, body="seeded-copy")

    assert module.main(["--root", str(workspaces), "--apply"]) == 0

    content = (personal_root / "dup" / "SKILL.md").read_text(encoding="utf-8")
    assert "flat-original" in content, "冲突时绝不能覆盖平铺那份"
    assert (personal_root / ".seed" / "dup").is_dir(), "冲突项应留在 .seed 等人工处理"


def test_repair_layout_is_idempotent(tmp_path):
    module = _load_repair_module()
    workspaces = tmp_path / "agent_workspaces"
    personal_root = workspaces / "u1" / "skills"
    _write_skill(personal_root, "seed-skill", seed=True)

    assert module.main(["--root", str(workspaces), "--apply"]) == 0
    assert module.main(["--root", str(workspaces), "--apply"]) == 0
    assert (personal_root / "seed-skill" / "SKILL.md").is_file()


# ── 6. 用户报告的直接症状：list_available_skills 返回 [] ────────────────


@pytest.mark.asyncio
async def test_list_available_skills_surfaces_seeded_personal_skill(tmp_path, monkeypatch):
    """技能都在 ``.seed`` 里时，``list_available_skills`` 不能返回空列表。

    这是用户在生产 K8s 环境报告的直接症状；该工具与沙箱策略无关，纯粹取决于
    ``list_skill_metas`` 能否看到历史遗留的 seed 布局。
    """
    from app.services.ai import skill_resolver
    from app.services.ai.tools.system_executive_tools import list_available_skills

    personal_root = tmp_path / "u1" / "skills"
    _write_skill(personal_root, "seed-skill", seed=True)
    monkeypatch.setattr(
        skill_resolver,
        "get_user_personal_skills_dir",
        lambda user_info=None: str(personal_root),
    )
    skill_resolver.clear_skill_meta_cache()

    async def _no_forbidden_skill_ids():
        return []

    monkeypatch.setattr(
        "app.services.ai.skills.policy.get_forbidden_skill_ids",
        _no_forbidden_skill_ids,
    )

    raw = await list_available_skills.ainvoke({})
    data = json.loads(raw)

    personal = [item for item in data if item.get("scope") == "personal"]
    assert [item["id"] for item in personal] == ["seed-skill"], (
        "个人技能躺在 .seed 里时，工具必须仍然列出它，而不是返回 []"
    )
