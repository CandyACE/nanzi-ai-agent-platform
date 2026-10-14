"""禁用命令关键字的解析行为：保存与徽标计数共用的唯一解析口径。

抽成共享函数是为了让「保存」与「tab 徽标计数」不再各写一份解析（两份必然漂移）。
分隔符集合按本次修复放宽：只认英文逗号时，中文逗号输入会存成一个永远不会被
shlex 命中的关键字——保存成功、界面无异常、运行时完全不拦截。
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


def test_parse_accepts_every_separator_a_human_would_type():
    """分隔符必须是「人真的会输入的那些」：中英文逗号、顿号、分号、换行。

    只认英文逗号时，「rm，shutdown」会存成一个永不命中 shlex 分词的关键字——
    保存成功、界面无异常、运行时完全不拦截，属于静默失效。
    """
    result = _run_typescript(
        """
return {
  chineseComma: api.parseForbiddenCommands('rm，shutdown'),
  enumerationComma: api.parseForbiddenCommands('rm、shutdown'),
  semicolon: api.parseForbiddenCommands('rm;shutdown'),
  newline: api.parseForbiddenCommands('rm\\nshutdown\\r\\nmv'),
  mixed: api.parseForbiddenCommands('rm，shutdown、mv;wget\\ncurl'),
  count: api.countForbiddenCommands('rm, shutdown, mv'),
  countEmpty: api.countForbiddenCommands(''),
};
"""
    )

    assert result["chineseComma"] == ["rm", "shutdown"]
    assert result["enumerationComma"] == ["rm", "shutdown"]
    assert result["semicolon"] == ["rm", "shutdown"]
    assert result["newline"] == ["rm", "shutdown", "mv"]
    assert result["mixed"] == ["rm", "shutdown", "mv", "wget", "curl"]
    assert result["count"] == 3
    assert result["countEmpty"] == 0


def test_parse_still_trims_and_drops_blank_items_across_separators():
    """换分隔符不能把既有的去空白 / 丢空项行为弄丢。"""
    result = _run_typescript(
        """
return {
  blanks: api.parseForbiddenCommands(' ，、;\\n '),
  padded: api.parseForbiddenCommands('  rm ，  shutdown  '),
  repeated: api.parseForbiddenCommands('rm,,,，；shutdown'),
};
"""
    )

    assert result["blanks"] == []
    assert result["padded"] == ["rm", "shutdown"]
    assert result["repeated"] == ["rm", "shutdown"]
