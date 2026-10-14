"""禁用资源组件的真渲染契约：`resource` 泛化后两种模式必须互斥。

源码里"写了 v-if/v-else"不等于渲染正确——注释夹在分支之间、分支写反、模板没编译进去，
都能骗过字符串断言。所以这里用 node + vue/compiler-sfc + @vue/server-renderer 真渲染组件
（harness：`tests/frontend/forbidden_tool_catalog_ssr.cjs`）。

范围：只钉"渲染了哪几个大组"、"文案随 resource 切换"、"orphan 区照旧独立"。SSR 不触发
onMounted、目录为空，所以候选的聚合 / 计数 / 全选 / 过滤仍由纯函数行为测试
（`test_forbidden_tool_grouping_behavior.py`）覆盖，接线由契约测试覆盖。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests/frontend/forbidden_tool_catalog_ssr.cjs"
pytestmark = pytest.mark.no_infrastructure


@pytest.fixture(scope="module")
def render_facts():
    proc = subprocess.run(
        ["node", str(HARNESS)],
        cwd=ROOT / "frontend",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


def test_tools_mode_is_unchanged_whether_or_not_resource_is_passed(render_facts):
    """默认 tools：不传 resource 与显式传 tools 必须逐项一致，工具侧行为零变化。"""
    default, explicit = render_facts["toolsDefault"], render_facts["toolsExplicit"]

    assert default == explicit, "不传 resource 必须与显式 resource=tools 完全一致"
    assert default["hasBuiltin"] is True
    assert default["hasDynamic"] is True
    assert default["hasSkills"] is False
    assert default["toolPlaceholder"] is True


def test_skills_mode_renders_only_the_public_skills_group(render_facts):
    """skills 模式只有一个大组：工具的两个大组一个都不许渲染出来。"""
    skills = render_facts["skills"]

    assert skills["hasSkills"] is True
    assert skills["hasBuiltin"] is False, "skills 模式不得渲染「选择要禁用的工具」"
    assert skills["hasDynamic"] is False, "skills 模式不得渲染「自定义 API 与 MCP 扩展工具禁用」"


def test_skills_mode_copy_switches_away_from_tool_wording(render_facts):
    """搜索框文案随 resource 切换，skills 模式不许继续提示「工具」。"""
    skills = render_facts["skills"]

    assert skills["skillPlaceholder"] is True
    assert skills["toolPlaceholder"] is False, "skills 模式的搜索框仍在提示「工具」"


def test_orphan_section_stays_independent_in_skills_mode(render_facts):
    """目录未加载（或加载失败）时，已禁用但查不到的技能仍要可见可解除，文案也不许说成工具。"""
    skills_orphan = render_facts["skillsWithOrphan"]

    assert skills_orphan["orphanTitle"] is True, "orphan 区必须与技能大组并列渲染"
    assert skills_orphan["hasSkills"] is True
    assert skills_orphan["hasBuiltin"] is False
    assert skills_orphan["orphanSaysSkill"] is True
    assert skills_orphan["orphanSaysTool"] is False

    tools_orphan = render_facts["toolsWithOrphan"]
    assert tools_orphan["orphanSaysTool"] is True, "工具模式的 orphan 文案不得被改掉"
    assert tools_orphan["orphanSaysSkill"] is False
