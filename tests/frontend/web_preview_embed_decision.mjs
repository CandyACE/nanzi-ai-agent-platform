// 用 Node 真跑「能否内嵌」决策纯函数。
//
// 核心回归：命中硬编码名单的站点只要**实测可嵌**就必须放行 —— 曾经的 bug 是
// www.baidu.com 被名单直接拦成提示卡片，用户点「仍尝试加载」又能正常打开。
// 字符串子串断言抓不到这种「先拦后又能开」，行为测试可以。
import assert from 'node:assert/strict'

import {
  hostnameOf,
  isKnownRestrictedHost,
  resolveEmbedDecision,
  KNOWN_RESTRICTED_DOMAINS,
} from '../../frontend/src/utils/webPreviewEmbed.ts'

let passed = 0
const check = (label, fn) => {
  fn()
  passed += 1
}

// --- 主机名解析 ---

check('hostnameOf 提取小写主机名', () => {
  assert.equal(hostnameOf('HTTPS://WWW.Baidu.com/s?wd=1'), 'www.baidu.com')
  assert.equal(hostnameOf('http://127.0.0.1:8001/x'), '127.0.0.1')
  assert.equal(hostnameOf('not a url'), '')
  assert.equal(hostnameOf(''), '')
  assert.equal(hostnameOf(null), '')
})

// --- 名单匹配（仅作降级用） ---

check('名单按后缀匹配且不误伤伪装域名', () => {
  assert.equal(isKnownRestrictedHost('baidu.com'), true)
  assert.equal(isKnownRestrictedHost('www.baidu.com'), true)
  assert.equal(isKnownRestrictedHost('m.baidu.com'), true)
  assert.equal(isKnownRestrictedHost('notbaidu.com'), false)
  assert.equal(isKnownRestrictedHost('baidu.com.evil.com'), false)
  assert.equal(isKnownRestrictedHost('example.com'), false)
  assert.equal(isKnownRestrictedHost(''), false)
})

// --- 实测优先：这是本次 bug 的修复点 ---

check('实测可嵌 → 名单命中也不拦（baidu 回归）', () => {
  const decision = resolveEmbedDecision('www.baidu.com', { embeddable: true })
  assert.equal(decision.blocked, false)
  assert.equal(decision.basis, 'probe')
})

check('实测受限 → 拦，且文案标明实测', () => {
  const decision = resolveEmbedDecision('github.com', {
    embeddable: false,
    reason: '目标站点通过 X-Frame-Options: deny 禁止内嵌',
    signals: { 'x-frame-options': 'deny' },
  })
  assert.equal(decision.blocked, true)
  assert.equal(decision.basis, 'probe')
  assert.match(decision.title, /实测|已确认/)
  assert.equal(decision.detail.includes('预判'), false)
  assert.equal(decision.signals['x-frame-options'], 'deny')
})

check('实测可嵌的非名单站点 → 不拦', () => {
  const decision = resolveEmbedDecision('example.com', { embeddable: true })
  assert.equal(decision.blocked, false)
  assert.equal(decision.basis, 'probe')
})

// --- 探测无结论时降级到名单，且文案必须说清是「预判」 ---

check('探测返回 null（不可达）→ 降级名单判定', () => {
  const hit = resolveEmbedDecision('www.baidu.com', { embeddable: null, reason: '探测超时' })
  assert.equal(hit.blocked, true)
  assert.equal(hit.basis, 'heuristic')
  assert.match(hit.title, /可能/)
  assert.match(hit.detail, /预判/)

  const miss = resolveEmbedDecision('example.com', { embeddable: null })
  assert.equal(miss.blocked, false)
  assert.equal(miss.basis, 'heuristic')
})

check('探测结果缺失/undefined → 同样降级，不得默认成受限', () => {
  for (const probe of [null, undefined]) {
    const hit = resolveEmbedDecision('github.com', probe)
    assert.equal(hit.blocked, true)
    assert.equal(hit.basis, 'heuristic')

    const miss = resolveEmbedDecision('example.com', probe)
    assert.equal(miss.blocked, false)
    assert.equal(miss.basis, 'heuristic')
  }
})

check('探测进行中 → 乐观放行，绝不先弹卡片再消失', () => {
  // 这是「先拦后又能加载」的观感来源：探测有网络延迟，
  // 期间若按名单预判拦住，用户就会看到卡片闪一下再变成网页。
  for (const host of ['www.baidu.com', 'github.com', 'example.com']) {
    const pending = resolveEmbedDecision(host, null, { pending: true })
    assert.equal(pending.blocked, false)
    assert.equal(pending.basis, 'probe')
  }
})

check('探测中优先于名单，实测结论优先于探测中', () => {
  const pending = resolveEmbedDecision('github.com', null, { pending: true })
  assert.equal(pending.blocked, false)

  const settled = resolveEmbedDecision('github.com', { embeddable: false })
  assert.equal(settled.blocked, true)
})

check('非名单站点探测失败 → 乐观放行（比误拦更可取）', () => {
  const decision = resolveEmbedDecision('unknown-blog.example.org', { embeddable: null })
  assert.equal(decision.blocked, false)
})

check('实测结论永远压过名单', () => {
  for (const host of ['github.com', 'www.baidu.com', 'example.com']) {
    assert.equal(resolveEmbedDecision(host, { embeddable: true }).blocked, false)
    assert.equal(resolveEmbedDecision(host, { embeddable: false }).blocked, true)
  }
})

// --- 契约细节 ---

check('名单是可注入的只读数组（降级口径可测试）', () => {
  assert.ok(Array.isArray(KNOWN_RESTRICTED_DOMAINS))
  assert.ok(KNOWN_RESTRICTED_DOMAINS.includes('github.com'))
  assert.equal(isKnownRestrictedHost('foo.test', ['test']), true)
})

check('决策对象结构稳定，空主机名不拦', () => {
  const decision = resolveEmbedDecision('', { embeddable: false })
  assert.equal(decision.blocked, false)

  const probe = resolveEmbedDecision('github.com', { embeddable: false })
  assert.equal(typeof probe.title, 'string')
  assert.equal(typeof probe.detail, 'string')
  assert.ok(probe.title.length > 0)
  assert.ok(probe.detail.length > 0)
})

console.log(`网页预览内嵌决策测试全部通过（${passed} 项）`)
