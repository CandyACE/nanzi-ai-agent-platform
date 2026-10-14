"""禁用目录请求去重（F11），纯函数行为测试。

每个配置页同时挂了 2 个 `ForbiddenToolCatalog` 实例（工具 / 技能），而两者请求的是
**同一个接口**（`GET /api/portal/tools/forbidden-catalog`，工具取 `candidates`、
技能取 `skill_candidates`）。打开一次弹窗就发两次完全相同的请求。

修法：模块级 in-flight 复用 + 短 TTL 缓存。取舍写在 `forbiddenCatalogCache.ts` 里，
这里只钉行为：并发只发一次、TTL 内复用、过期/显式失效后重取、失败绝不缓存。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/forbiddenCatalogCache.ts"
pytestmark = pytest.mark.no_infrastructure

HARNESS = """
(async () => {
const fs = require('fs');
const path = require('path');
const ts = require('./frontend/node_modules/typescript');
const loaded = new Map();
const loadModule = (absolute) => {
  if (loaded.has(absolute)) return loaded.get(absolute).exports;
  const source = fs.readFileSync(absolute, 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
  }).outputText;
  const moduleRef = { exports: {} };
  loaded.set(absolute, moduleRef);
  const localRequire = (id) => {
    if (id.startsWith('.')) {
      const base = path.resolve(path.dirname(absolute), id);
      const hit = [base, base + '.ts', base + '.js'].find(
        (candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile(),
      );
      if (hit) return loadModule(hit);
    }
    return require(id);
  };
  new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, localRequire);
  return moduleRef.exports;
};
const api = loadModule(path.resolve(__MODULE__));
const tick = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const snapshot = (n) => ({ candidates: [{ id: 'tool-' + n, label: '', description: '' }], skillCandidates: [] });
const result = await (async () => { __EXPRESSION__ })();
process.stdout.write(JSON.stringify(result));
})().catch(error => { console.error(error); process.exit(1); });
"""


def _run_typescript(expression: str):
    script = HARNESS.replace("__MODULE__", json.dumps(MODULE)).replace("__EXPRESSION__", expression)
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_concurrent_calls_share_one_in_flight_request():
    """同一时刻到达的两次加载共用一个 in-flight Promise——只发一次请求。"""
    result = _run_typescript(
        """
let calls = 0;
const fetcher = async () => { calls += 1; await tick(20); return snapshot(calls); };
const [first, second] = await Promise.all([
  api.loadForbiddenCatalog(fetcher),
  api.loadForbiddenCatalog(fetcher),
]);
return {
  calls,
  sameSnapshot: first === second,
  firstTool: first.candidates[0].id,
  peeked: api.peekForbiddenCatalog() === first,
};
"""
    )

    assert result["calls"] == 1
    assert result["sameSnapshot"] is True
    assert result["firstTool"] == "tool-1"
    assert result["peeked"] is True


def test_short_ttl_reuses_recent_result_then_refetches():
    """TTL 内复用（关掉再打开弹窗不重复请求），过期后必须重新请求——避免陈旧候选。"""
    result = _run_typescript(
        """
let calls = 0;
let now = 0;
const options = { ttlMs: 1000, now: () => now };
const fetcher = async () => { calls += 1; return snapshot(calls); };
await api.loadForbiddenCatalog(fetcher, options);
await api.loadForbiddenCatalog(fetcher, options);
now = 500;
await api.loadForbiddenCatalog(fetcher, options);
const withinTtl = calls;
now = 1001;
const afterTtl = await api.loadForbiddenCatalog(fetcher, options);
return { withinTtl, calls, afterTtlTool: afterTtl.candidates[0].id, ttlConstant: api.FORBIDDEN_CATALOG_TTL_MS };
"""
    )

    assert result["withinTtl"] == 1, "TTL 内不该重复请求"
    assert result["calls"] == 2, "TTL 过期后必须重新请求"
    assert result["afterTtlTool"] == "tool-2"
    assert 0 < result["ttlConstant"] <= 60_000, "TTL 必须是短缓存，不能退化成永久缓存"


def test_failure_is_never_cached():
    """失败既不缓存也不通知订阅者：下次打开必须重试，否则用户会永远看到空目录。"""
    result = _run_typescript(
        """
let calls = 0;
const seen = [];
api.subscribeForbiddenCatalog((value) => seen.push(value.candidates.length));
const failing = async () => { calls += 1; throw new Error('boom'); };
const succeeding = async () => { calls += 1; return snapshot(1); };
await api.loadForbiddenCatalog(failing).catch(() => 'failed');
const afterFirstFailure = calls;
await api.loadForbiddenCatalog(failing).catch(() => 'failed');
const afterSecondFailure = calls;
const peekAfterFailure = api.peekForbiddenCatalog();
const success = await api.loadForbiddenCatalog(succeeding);
const afterSuccess = calls;
await api.loadForbiddenCatalog(succeeding);
return {
  afterFirstFailure,
  afterSecondFailure,
  afterSuccess,
  afterCachedSuccess: calls,
  peekAfterFailure,
  notified: seen.length,
  recovered: success.candidates[0].id,
};
"""
    )

    assert result["afterFirstFailure"] == 1
    assert result["afterSecondFailure"] == 2, "上一次失败不得被当成缓存，必须重新请求"
    assert result["afterSuccess"] == 3
    assert result["afterCachedSuccess"] == 3, "成功结果在 TTL 内复用"
    assert result["peekAfterFailure"] is None
    assert result["notified"] == 1, "只有成功加载才通知"
    assert result["recovered"] == "tool-1"


def test_invalidate_forces_refetch_and_unsubscribe_stops_notifications():
    """显式失效后重取；退订后回调不再触发（页面卸载必须能退订，否则重复渲染）。"""
    result = _run_typescript(
        """
let calls = 0;
const seen = [];
const fetcher = async () => { calls += 1; return snapshot(calls); };
api.subscribeForbiddenCatalog(() => {});
const unsubscribe = api.subscribeForbiddenCatalog((value) => seen.push(value.candidates[0].id));
await api.loadForbiddenCatalog(fetcher);
api.invalidateForbiddenCatalog();
await api.loadForbiddenCatalog(fetcher, { ttlMs: 60_000 });
unsubscribe();
api.invalidateForbiddenCatalog();
await api.loadForbiddenCatalog(fetcher, { ttlMs: 60_000 });
return { calls, seen };
"""
    )

    assert result["calls"] == 3
    assert result["seen"] == ["tool-1", "tool-2"], "退订后不再收到通知"


def test_fetchers_returning_bad_shapes_are_normalized_to_empty_lists():
    """接口返回坏形状（缺字段 / 非数组）时归一成空数组，调用方不必各自防御。"""
    result = _run_typescript(
        """
api.invalidateForbiddenCatalog();
const first = await api.loadForbiddenCatalog(async () => ({ candidates: 'nope' }));
api.invalidateForbiddenCatalog();
const second = await api.loadForbiddenCatalog(async () => ({}));
return {
  firstCandidates: first.candidates,
  firstSkills: first.skillCandidates,
  secondCandidates: second.candidates,
  secondSkills: second.skillCandidates,
};
"""
    )

    assert result["firstCandidates"] == []
    assert result["firstSkills"] == []
    assert result["secondCandidates"] == []
    assert result["secondSkills"] == []
