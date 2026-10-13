"""禁用命令关键字的解析行为：与保存流程原本的内联实现逐字等价。

抽成共享函数是为了让「保存」与「tab 徽标计数」不再各写一份解析（两份必然漂移）。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/forbiddenCommands.ts"
pytestmark = pytest.mark.no_infrastructure


def _run_typescript(expression: str):
    script = f"""
(async () => {{
const fs = require('fs');
const ts = require('./frontend/node_modules/typescript');
const source = fs.readFileSync({json.dumps(MODULE)}, 'utf8');
const code = ts.transpileModule(source, {{
  compilerOptions: {{ module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }}
}}).outputText;
const moduleRef = {{ exports: {{}} }};
new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, require);
const api = moduleRef.exports;
const result = await (async () => {{ {expression} }})();
process.stdout.write(JSON.stringify(result));
}})().catch(error => {{ console.error(error); process.exit(1); }});
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_parse_splits_trims_and_drops_blanks():
    result = _run_typescript(
        """
return {
  mixed: api.parseForbiddenCommands('rm, shutdown , ,mv'),
  empty: api.parseForbiddenCommands(''),
  blanks: api.parseForbiddenCommands(' , , '),
  missing: api.parseForbiddenCommands(null),
  single: api.parseForbiddenCommands('rm'),
};
"""
    )

    assert result["mixed"] == ["rm", "shutdown", "mv"]
    assert result["empty"] == []
    assert result["blanks"] == []
    assert result["missing"] == []
    assert result["single"] == ["rm"]


def test_parse_matches_the_original_inline_semantics():
    """原实现只按英文逗号切分：中文逗号仍属于命令的一部分，不得"顺便"改掉。"""
    result = _run_typescript(
        """
return {
  chineseComma: api.parseForbiddenCommands('rm，shutdown'),
  count: api.countForbiddenCommands('rm, shutdown, mv'),
  countEmpty: api.countForbiddenCommands(''),
};
"""
    )

    assert result["chineseComma"] == ["rm，shutdown"]
    assert result["count"] == 3
    assert result["countEmpty"] == 0
