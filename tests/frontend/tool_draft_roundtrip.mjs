import assert from 'node:assert/strict'
import { parseRequestInput } from '../../frontend/src/utils/toolImport.ts'
import { buildDraftParams, buildDraftSchema, buildLocationMap, resolveParamLocation } from '../../frontend/src/utils/toolDraft.ts'
import { parseToolSchema } from '../../frontend/src/utils/toolSchema.ts'

let passed = 0
const check = (label, fn) => { fn(); passed += 1; console.log('  ✓ ' + label) }

check('落位：地址里的占位符永远算 path，与请求方法无关', () => {
  assert.equal(resolveParamLocation('GET', 'https://x/{id}', 'id'), 'path')
  assert.equal(resolveParamLocation('POST', 'https://x/{id}', 'id'), 'path')
  assert.equal(resolveParamLocation('PATCH', 'https://x/{id}', 'id'), 'path')
})

check('落位：GET 的其余参数走 query，非 GET 走 body（与运行时一致）', () => {
  assert.equal(resolveParamLocation('GET', 'https://x/a', 'city'), 'query')
  assert.equal(resolveParamLocation('POST', 'https://x/a', 'amount'), 'body')
  assert.equal(resolveParamLocation('PUT', 'https://x/a', 'amount'), 'body')
  assert.equal(resolveParamLocation('DELETE', 'https://x/a', 'amount'), 'body')
})

check('必填：占位符参数必填，且不带默认值', () => {
  const params = buildDraftParams(parseRequestInput('https://api.test/v1/orders/{order_id}/refund'))
  assert.equal(params.length, 1)
  assert.equal(params[0].name, 'order_id')
  assert.equal(params[0].location, 'path')
  assert.equal(params[0].required, true)
  assert.equal(params[0].defaultValue, '')
})

check('必填：URL 里带了值的参数自动变可选 + 默认值', () => {
  const params = buildDraftParams(parseRequestInput('https://api.test/w?city=北京&days=3'))
  const city = params.find((p) => p.name === 'city')
  assert.equal(city.required, false)
  assert.equal(city.defaultValue, '北京')
  assert.equal(city.type, 'string')
  assert.equal(city.location, 'query')
  const days = params.find((p) => p.name === 'days')
  assert.equal(days.required, false)
  assert.equal(days.defaultValue, '3')
})

check('必填：query 里没给值的参数判为必填', () => {
  const params = buildDraftParams(parseRequestInput('https://api.test/w?city='))
  assert.equal(params[0].required, true)
  assert.equal(params[0].defaultValue, '')
})

check('query 里的 {b} 是「要模型填值」而不是路径替换：必填且落位 query', () => {
  // 这是第一版写错的地方：把 query 里的占位符也当成 pathParams 会让界面标错落位，
  // 而在 buildDraftParams 里「跳过占位符」又会把这个参数整个丢掉。
  const params = buildDraftParams(parseRequestInput('https://x.test/s?b={b}'))
  assert.equal(params.length, 1)
  assert.equal(params[0].name, 'b')
  assert.equal(params[0].location, 'query')
  assert.equal(params[0].required, true)
})

check('重复同名参数只保留第一次出现的', () => {
  const params = buildDraftParams(parseRequestInput('https://x.test/s?tag=a&tag=b'))
  assert.deepEqual(params.map((p) => p.name), ['tag'])
  assert.equal(params[0].defaultValue, 'a')
})

check('类型：从请求体的 JSON 值推断，而不是一律 string', () => {
  const parsed = parseRequestInput(
    `curl -X POST https://api.test/o -d '{"amount": 100, "ratio": 1.5, "ok": true, "tags": ["a"], "meta": {"x": 1}}'`,
  )
  const params = buildDraftParams(parsed)
  const typeOf = (name) => params.find((p) => p.name === name).type
  assert.equal(typeOf('amount'), 'integer')
  assert.equal(typeOf('ratio'), 'number')
  assert.equal(typeOf('ok'), 'boolean')
  assert.equal(typeOf('tags'), 'array')
  assert.equal(typeOf('meta'), 'object')
})

check('body 里带了值的参数同样变可选 + 默认值', () => {
  const params = buildDraftParams(parseRequestInput(`curl -X POST https://api.test/o -d '{"amount": 100}'`))
  assert.equal(params[0].location, 'body')
  assert.equal(params[0].required, false)
  assert.equal(params[0].defaultValue, '100')
})

check('生成结果能被 toolSchema 往返而不变形（扁平形态）', () => {
  const parsed = parseRequestInput(
    `curl -X POST 'https://api.test/v1/orders/{order_id}/refund' -d '{"amount": 100}'`,
  )
  const schema = buildDraftSchema(buildDraftParams(parsed))
  const parsedSchema = parseToolSchema(schema)
  assert.equal(parsedSchema.shape, 'flat')
  assert.deepEqual(parsedSchema.params.map((p) => [p.name, p.type, p.required]), [
    ['order_id', 'string', true],
    ['amount', 'integer', false],
  ])
  // 非必填必须落成内联 required:false，否则运行时按缺省必填处理
  assert.equal(JSON.parse(schema).amount.required, false)
  assert.equal(JSON.parse(schema).amount.default, 100)
})

check('参数名为空白的行不会写进 schema', () => {
  const schema = buildDraftSchema([
    { name: '   ', type: 'string', required: true, description: '', defaultValue: '', location: 'query', reason: '' },
  ])
  assert.deepEqual(JSON.parse(schema), {})
})

check('落位映射供界面显示标签', () => {
  const params = buildDraftParams(parseRequestInput(`curl -X POST 'https://x.test/{id}/go?flag=1' -d '{"n": 2}'`))
  assert.deepEqual(buildLocationMap(params), { id: 'path', flag: 'body', n: 'body' })
})

check('每一行都带「为什么这么判」的理由，界面不用自己拼文案', () => {
  const params = buildDraftParams(parseRequestInput('https://api.test/w?city=北京&days='))
  for (const param of params) {
    assert.ok(param.reason && param.reason.length > 0, `${param.name} 缺少理由`)
  }
})

console.log(`\n工具草稿往返测试全部通过（${passed} 项）`)
