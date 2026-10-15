import assert from 'node:assert/strict'
import { parseRequestInput } from '../../frontend/src/utils/toolImport.ts'

let passed = 0
const check = (label, fn) => { fn(); passed += 1; console.log('  ✓ ' + label) }

check('curl：多行续行 + -X + 两个 -H + -d JSON 体', () => {
  const r = parseRequestInput(`curl -X POST 'https://api.example.com/v1/orders/{order_id}/refund' \\
  -H 'Authorization: Bearer sk-xxx' \\
  -H 'Content-Type: application/json' \\
  -d '{"amount": 100, "reason": "客户申请"}'`)
  assert.equal(r.error, undefined)
  assert.equal(r.method, 'POST')
  assert.equal(r.urlTemplate, 'https://api.example.com/v1/orders/{order_id}/refund')
  assert.deepEqual(r.pathParams, ['order_id'])
  assert.equal(r.headers['Authorization'], 'Bearer sk-xxx')
  assert.equal(r.headers['Content-Type'], 'application/json')
  assert.deepEqual(
    r.bodyParams.map((p) => [p.name, p.value, p.type]),
    [['amount', '100', 'integer'], ['reason', '客户申请', 'string']],
  )
})

check('curl：--url 与 -H 双引号写法', () => {
  const r = parseRequestInput(`curl --url https://x.test/a -X PUT -H "X-K: v" -d '{"n": 1}'`)
  assert.equal(r.method, 'PUT')
  assert.equal(r.urlTemplate, 'https://x.test/a')
  assert.equal(r.headers['X-K'], 'v')
  assert.equal(r.bodyParams[0].name, 'n')
})

check('curl：没有 -X 也没 -d 时默认 GET', () => {
  const r = parseRequestInput(`curl 'https://x.test/list?a=1'`)
  assert.equal(r.method, 'GET')
  assert.deepEqual(r.queryParams.map((p) => [p.name, p.value]), [['a', '1']])
})

check('curl：-d 非 JSON 体不猜，降级为警告', () => {
  const r = parseRequestInput(`curl -X POST https://x.test/a -d 'a=1&b=2'`)
  assert.equal(r.error, undefined)
  assert.equal(r.bodyParams.length, 0)
  assert.ok(r.warnings.some((w) => w.includes('请求体')))
})

check('纯 URL：query 与占位符', () => {
  const r = parseRequestInput('https://api.example.com/v1/weather?city={city}&days=3&units=metric')
  assert.equal(r.method, 'GET')
  assert.equal(r.urlTemplate, 'https://api.example.com/v1/weather')
  assert.deepEqual(r.queryParams.map((p) => [p.name, p.value]), [
    ['city', '{city}'], ['days', '3'], ['units', 'metric'],
  ])
})

check('query：无值、重复参数、百分号编码都能读出', () => {
  const r = parseRequestInput('https://x.test/s?flag&tag=a&tag=b&q=%E5%8C%97%E4%BA%AC')
  assert.deepEqual(r.queryParams.map((p) => [p.name, p.value]), [
    ['flag', ''], ['tag', 'a'], ['tag', 'b'], ['q', '北京'],
  ])
})

check('非法百分号编码不抛异常，保留原文', () => {
  const r = parseRequestInput('https://x.test/s?q=100%zz')
  assert.equal(r.error, undefined)
  assert.equal(r.queryParams[0].value, '100%zz')
})

check('缺 scheme 时补 https:// 并给警告', () => {
  const r = parseRequestInput('api.example.com/v1/x?a=1')
  assert.equal(r.error, undefined)
  assert.equal(r.urlTemplate, 'https://api.example.com/v1/x')
  assert.ok(r.warnings.some((w) => w.includes('https://')))
})

check('识别不出地址时返回 error，绝不抛异常', () => {
  assert.ok(parseRequestInput('').error)
  assert.ok(parseRequestInput('随便一段中文').error)
  assert.ok(parseRequestInput('curl -X POST').error)
})

check('path 占位符与 query 占位符各归各位', () => {
  // path 里的 {a} 由运行时做路径替换；query 里的 {b} 不是路径替换，
  // 它只是一个「需要模型填值」的查询参数——混进 pathParams 会让界面标错落位。
  const r = parseRequestInput('https://x.test/{a}/y?b={b}&c=3')
  assert.deepEqual(r.pathParams, ['a'])
  assert.deepEqual(r.queryParams.map((p) => [p.name, p.value]), [['b', '{b}'], ['c', '3']])
})

check('非 GET 且带 query 参数时给出落位警告', () => {
  // 运行时把非 GET 的其余参数一律放进 JSON body，而 url_template 已被剥掉 query，
  // 所以「POST 的查询参数」实际会变成请求体字段——必须让使用者知道。
  const r = parseRequestInput(`curl -X POST 'https://x.test/a?flag=1' -d '{"n": 1}'`)
  assert.ok(r.warnings.some((w) => w.includes('请求体')))
})

check('不支持的方法被明确标出', () => {
  const r = parseRequestInput('curl -X HEAD https://x.test/a')
  assert.equal(r.method, 'HEAD')
  assert.ok(r.warnings.some((w) => w.includes('不支持')))
})

check('暂不支持的 curl 开关被忽略但有提示', () => {
  const r = parseRequestInput('curl -G https://x.test/a?b=1')
  assert.equal(r.error, undefined)
  assert.ok(r.warnings.some((w) => w.includes('-G')))
})

console.log(`\n工具导入往返测试全部通过（${passed} 项）`)
