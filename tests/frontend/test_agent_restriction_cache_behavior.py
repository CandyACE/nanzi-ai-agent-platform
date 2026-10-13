"""智能体级限制的请求去重缓存（沿用 forbiddenCatalogCache 的模式）。

为什么需要：权限弹框里「智能体」那一排卡片都要显示已禁数量角标，弹框打开时也可能
和卡片加载撞在同一时刻。没有去重就会对同一个 (作用域, 智能体) 连打多次 GET。

取舍与 `forbiddenCatalogCache.ts` 完全一致：in-flight 复用 + 短 TTL（30s）+ 失败不缓存，
另加一个「保存成功后回填」入口——PUT 已经知道自己写了什么，没必要再 GET 一次。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/agentRestrictionCache.ts"
pytestmark = pytest.mark.no_infrastructure

# 多模块 harness：缓存模块 import 同目录的 agentRestrictions，需要相对路径解析
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
const lists = (tool) => ({ forbidden_tools: [tool], forbidden_skills: [] });
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


def test_concurrent_loads_share_one_request_per_key():
    """同一 (作用域, 智能体) 的并发加载共用一个 in-flight Promise；不同智能体各自请求。"""
    result = _run_typescript(
        """
let calls = 0;
const fetcher = async () => { calls += 1; await tick(20); return lists('calls-' + calls); };
const [first, second] = await Promise.all([
  api.loadAgentRestriction('user:7:agent-1', fetcher),
  api.loadAgentRestriction('user:7:agent-1', fetcher),
]);
await api.loadAgentRestriction('user:7:agent-2', fetcher);
return {
  calls,
  first: first.forbidden_tools,
  second: second.forbidden_tools,
  sameReference: first === second,
  secondAgent: api.peekAgentRestriction('user:7:agent-2').forbidden_tools,
};
"""
    )

    assert result["calls"] == 2, "同一 key 的并发只发一次；另一个智能体各自发一次"
    assert result["first"] == result["second"] == ["calls-1"]
    assert result["secondAgent"] == ["calls-2"]


def test_scope_is_part_of_the_cache_key():
    """用户与角色、不同用户/角色之间不得互相读到对方的限制。"""
    result = _run_typescript(
        """
let calls = 0;
const fetcher = async (tool) => { calls += 1; return lists(tool); };
const userA = await api.loadAgentRestriction('user:1:agent-1', () => fetcher('user-1'));
const userB = await api.loadAgentRestriction('user:2:agent-1', () => fetcher('user-2'));
const roleA = await api.loadAgentRestriction('role:1:agent-1', () => fetcher('role-1'));
return {
  calls,
  userA: userA.forbidden_tools,
  userB: userB.forbidden_tools,
  roleA: roleA.forbidden_tools,
};
"""
    )

    assert result["calls"] == 3, "作用域不同 -> 必须各自请求"
    assert (result["userA"], result["userB"], result["roleA"]) == (["user-1"], ["user-2"], ["role-1"])


def test_ttl_reuse_expiry_and_explicit_invalidate():
    """TTL 内复用同一份内存快照，过期或显式失效后重新请求。"""
    result = _run_typescript(
        """
let calls = 0;
let clock = 1000;
const options = { ttlMs: 100, now: () => clock };
const fetcher = async () => { calls += 1; return lists('v' + calls); };
const first = await api.loadAgentRestriction('user:7:agent-1', fetcher, options);
const cached = await api.loadAgentRestriction('user:7:agent-1', fetcher, options);
clock = 1100;
const expired = await api.loadAgentRestriction('user:7:agent-1', fetcher, options);
api.invalidateAgentRestriction('user:7:agent-1');
const afterInvalidate = await api.loadAgentRestriction('user:7:agent-1', fetcher, options);
return {
  calls,
  first: first.forbidden_tools,
  cached: cached.forbidden_tools,
  expired: expired.forbidden_tools,
  afterInvalidate: afterInvalidate.forbidden_tools,
};
"""
    )

    assert result["first"] == result["cached"] == ["v1"], "TTL 内不重复打网"
    assert result["expired"] == ["v2"], "TTL 到期必须重新拉取"
    assert result["afterInvalidate"] == ["v3"], "显式失效后必须重新拉取"
    assert result["calls"] == 3


def test_failures_are_never_cached():
    """失败绝不写缓存：一次网络抖动不该让用户在整个 TTL 窗口里看到空限制（=已清空）。"""
    result = _run_typescript(
        """
let calls = 0;
const fetcher = async () => {
  calls += 1;
  if (calls === 1) throw new Error('boom');
  return lists('ok');
};
let firstError = '';
try {
  await api.loadAgentRestriction('user:7:agent-1', fetcher);
} catch (error) {
  firstError = String(error.message || error);
}
const peekedAfterFailure = api.peekAgentRestriction('user:7:agent-1');
const retried = await api.loadAgentRestriction('user:7:agent-1', fetcher);
return { calls, firstError, peekedAfterFailure, retried: retried.forbidden_tools };
"""
    )

    assert result["calls"] == 2, "失败后下一次必须真实重试"
    assert result["firstError"] == "boom"
    assert result["peekedAfterFailure"] is None, "失败不得留下空快照"
    assert result["retried"] == ["ok"]


def test_saved_payload_is_written_back_to_the_cache():
    """PUT 成功后回填：角标立刻正确，重新打开弹框也不必再 GET。"""
    result = _run_typescript(
        """
let calls = 0;
const fetcher = async () => { calls += 1; return lists('from-server'); };
const written = api.writeAgentRestriction('user:7:agent-1', {
  forbidden_tools: ['a', 'a', ' '],
  forbidden_skills: null,
});
const afterWrite = await api.loadAgentRestriction('user:7:agent-1', fetcher);
return {
  calls,
  written,
  afterWrite: afterWrite.forbidden_tools,
  scopedWrite: api.peekAgentRestriction('role:7:agent-1'),
};
"""
    )

    assert result["calls"] == 0, "回填后再加载不得再打网"
    assert result["written"] == {"forbidden_tools": ["a"], "forbidden_skills": []}
    assert result["afterWrite"] == ["a"]
    assert result["scopedWrite"] is None, "回填只影响该 (作用域, 智能体) 槽位"


def test_catalog_loads_are_deduped_per_scope_and_agent():
    """候选清单按「视角 + 智能体」去重：同一个键只发一次，坏形状归一成空分组。

    键必须带视角：`forbidden_globally` 是相对该用户 / 角色算的，只按 agent_id 缓存
    会把一个用户的置灰结果带给另一个用户（键由 agentRestrictableCatalogCacheKey 生成）。
    """
    result = _run_typescript(
        """
let calls = 0;
const fetcher = async () => {
  calls += 1;
  return { agent_id: 'agent-1', groups: [{ key: 'builtin_tools', label: '内置工具', items: [{ id: 'read_file', label: 'read_file' }] }] };
};
const keyUserA = 'catalog:user:1:agent-1';
const keyUserB = 'catalog:user:2:agent-1';
const [first, second] = await Promise.all([
  api.loadAgentRestrictableCatalog(keyUserA, fetcher),
  api.loadAgentRestrictableCatalog(keyUserA, fetcher),
]);
await api.loadAgentRestrictableCatalog(keyUserB, fetcher);
const bad = await api.loadAgentRestrictableCatalog('catalog:user:1:agent-2', async () => null);
return {
  calls,
  groups: first.map((group) => group.key),
  sameReference: first === second,
  peeked: api.peekAgentRestrictableCatalog(keyUserA).map((group) => group.key),
  otherScope: api.peekAgentRestrictableCatalog(keyUserB).map((group) => group.key),
  bad: bad.length,
  peekedBad: api.peekAgentRestrictableCatalog('catalog:user:1:agent-2').length,
};
"""
    )

    assert result["calls"] == 2, (
        "同一键的并发只发一次；另一个视角另发一次（agent-2 用的是不会计数的 fetcher）"
    )
    assert result["groups"] == ["builtin_tools"]
    assert result["sameReference"] is True, "同一键的并发必须共用同一个 Promise 的结果"
    assert result["peeked"] == ["builtin_tools"]
    assert result["otherScope"] == ["builtin_tools"], "不同视角各自缓存，互不覆盖"
    assert result["bad"] == 0 and result["peekedBad"] == 0
