"""布尔型系统配置必须渲染成开关，不能退化成手填 true/false 的文本框。

**背景**：`miniprogram_enabled` 曾漏进 `SystemConfig.vue` 的开关白名单，导致管理员
要在文本框里手输 `false`——而平台上已有 12 个同类布尔配置早就是胶囊开关了。
这类「新增配置忘了注册成开关」的遗漏只靠肉眼 review 兜不住，故固化为契约测试。

开关在本仓库有**两种形态**，本测试都覆盖：
1. 白名单数组：`v-else-if="['a','b'].includes(item.key)"`
2. 专门分支：`v-else-if="item.key === 'x'"`，且分支体内真的写了 `item.value === 'true'` 的切换
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/views/SystemConfig.vue"

# 专门分支的判定窗口：从 `item.key === 'x'` 往后取这么多字符找切换逻辑。
# 实测 hide_login_apikey 的切换语句就在其分支开头附近，500 足够且不易误伤。
_BRANCH_BODY_WINDOW = 500


def _boolean_config_keys() -> set[str]:
    """从两套迁移里取出所有「值为 true/false」的 system_configs key。"""
    keys: set[str] = set()
    for directory in ("db-prod", "db-prod-pg"):
        for sql_path in sorted((ROOT / directory).glob("*.sql")):
            text = sql_path.read_text(encoding="utf-8", errors="ignore")
            for statement in re.findall(
                r"INSERT[^;]*?system_configs[^;]*?;", text, re.S | re.I
            ):
                keys.update(
                    re.findall(r"'([a-z_0-9]+)'\s*,\s*'(?:true|false)'", statement, re.I)
                )
    return keys


def _toggle_keys() -> set[str]:
    """SystemConfig.vue 里实际被开关分支覆盖的 key（两种形态）。"""
    view = VIEW.read_text(encoding="utf-8")
    keys: set[str] = set()

    # 形态一：显式白名单数组
    for group in re.findall(r"\[([^\]]*?)\]\.includes\(item\.key\)", view):
        keys.update(re.findall(r"'([a-z_0-9]+)'", group))

    # 形态二：专门分支，且分支体内确有开关切换逻辑
    for match in re.finditer(r"item\.key === '([a-z_0-9]+)'", view):
        body = view[match.end() : match.end() + _BRANCH_BODY_WINDOW]
        if "item.value === 'true'" in body:
            keys.add(match.group(1))

    return keys


def test_view_exists():
    assert VIEW.exists(), f"找不到 {VIEW}"


def test_boolean_config_keys_are_discoverable():
    """自检：解析不出布尔配置说明本测试已失效，必须显式报错而不是静默放行。"""
    keys = _boolean_config_keys()
    assert len(keys) >= 10, f"只解析出 {len(keys)} 个布尔配置，解析逻辑可能已失效"


def test_miniprogram_enabled_renders_as_toggle():
    """微端开关必须走开关分支（本次遗漏的回归守卫）。"""
    assert "miniprogram_enabled" in _toggle_keys(), (
        "miniprogram_enabled 未出现在 SystemConfig.vue 的任何开关分支里，"
        "会渲染成手填 true/false 的文本框"
    )


def test_every_boolean_config_renders_as_toggle():
    """通用守卫：任何布尔配置都必须有对应的开关分支。"""
    missing = sorted(_boolean_config_keys() - _toggle_keys())
    assert not missing, (
        "以下布尔配置会渲染成手填 true/false 的文本框，"
        "请把它们注册进 SystemConfig.vue 的开关白名单（或补专门分支）：\n  "
        + "\n  ".join(missing)
    )
