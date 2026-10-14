"""技能 ``enabled`` 的前端口径必须与后端 ``is_skill_enabled`` 逐字一致。

``enabled`` 是 frontmatter 里的字符串，人工编辑时完全可能写成 ``False`` / ``0`` /
``yes``。后端只认 ``{1,true,yes,on}`` 这一套真值白名单，而前端此前有 4 套口径，
**两个方向都会骗人**：

* ``enabled: "False"``：后端判定禁用，前端 ``!== 'false'`` 却认成启用 → 管理界面显示
  「已启用」、会话里也能勾选，但运行时根本不加载，用户以为开关坏了；
* ``enabled: "yes"``：后端判定启用，会话资源菜单的白名单只认 ``true/1`` → 技能被
  过滤掉，明明启用了却从列表消失，无从勾选。

这组契约钉住三件事：白名单与后端同源、五个消费点都走统一入口、旧口径不再回头。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
HELPER = FRONTEND / "utils" / "skillEnabled.ts"
BACKEND = ROOT / "app" / "utils" / "skill_metadata.py"

CONSUMERS = [
    "views/SkillsManagement.vue",
    "components/embed/SkillCascadeMenu.vue",
    "views/AgentManagement.vue",
    "views/EmbedChat.vue",
    "components/task/TaskPromptComposer.vue",
]


def test_helper_truthy_flags_match_backend():
    """真值白名单必须与后端 ``_TRUTHY_FLAGS`` 完全相同。"""
    helper_text = HELPER.read_text(encoding="utf-8")
    backend_text = BACKEND.read_text(encoding="utf-8")
    front = re.search(r"TRUTHY_FLAGS = new Set\(\[([^\]]+)\]\)", helper_text)
    back = re.search(r"_TRUTHY_FLAGS = frozenset\(\{([^}]+)\}\)", backend_text)
    assert front and back

    def parse(raw: str) -> set[str]:
        return {item.strip().strip("'\"") for item in raw.split(",") if item.strip()}

    assert parse(front.group(1)) == parse(back.group(1)), (
        "前端技能启用白名单与后端 is_skill_enabled 不一致，界面状态会和实际生效相反"
    )


def test_helper_handles_bool_null_and_case():
    """判定必须能处理布尔、null/undefined 与任意大小写——这三类都是实际出现过的数据。"""
    text = HELPER.read_text(encoding="utf-8")
    assert "typeof enabled === 'boolean'" in text, (
        "显式布尔必须先短路，否则 String(true) 会走到白名单"
    )
    assert "enabled === null || enabled === undefined" in text, (
        "缺失必须回落到默认值而非判定为禁用"
    )
    assert "toLowerCase()" in text, "手写 False/TRUE 必须能识别"
    assert "trim()" in text, "frontmatter 值可能带空格"


def test_all_consumers_use_the_shared_helper():
    for rel in CONSUMERS:
        text = (FRONTEND / rel).read_text(encoding="utf-8")
        assert "import { isSkillEnabled } from '@/utils/skillEnabled'" in text, (
            f"{rel} 未接入统一判定"
        )
        assert "isSkillEnabled(" in text, f"{rel} 导入了却没有使用"


def test_legacy_enabled_comparisons_do_not_come_back():
    """旧口径是这次修的根因，必须防止回归。"""
    legacy = [
        r"\.enabled === 'false'",
        r"\.enabled !== 'false'",
        r"String\(s\.enabled \?\? 'true'\) !== 'false'",
        r"\.enabled === false \|\| .*\.enabled === '0'",
    ]
    offenders = []
    for path in list(FRONTEND.rglob("*.vue")) + list(FRONTEND.rglob("*.ts")):
        if path == HELPER:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in legacy:
            if re.search(pattern, text):
                offenders.append(f"{path.relative_to(FRONTEND)}: {pattern}")
    assert not offenders, "技能 enabled 判定又出现了就地比较：\n" + "\n".join(offenders)


def test_toggle_still_writes_frontmatter_strings():
    """统一判定不能顺手把写回值改成布尔——toggle 接口要的是 'true'/'false' 字符串。"""
    text = (FRONTEND / "views/SkillsManagement.vue").read_text(encoding="utf-8")
    assert "const newStatus = !isSkillEnabled(skill.enabled) ? 'true' : 'false'" in text
    assert "/toggle?enabled=${newStatus === 'true'}" in text
