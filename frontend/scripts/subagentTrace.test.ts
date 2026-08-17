import assert from 'node:assert/strict'
import {
  formatSubagentTraceSummary,
  normalizeSubagentTraceMeta,
  subagentDisplayName,
} from '../src/utils/subagentTrace.ts'

const meta = normalizeSubagentTraceMeta({
  display_name: '知识库助手',
  run_id: 'subrun_test',
  child_trace_id: 'sub_child',
  stop_reason: 'completed',
  tool_filter: ['search_knowledge_base'],
})

assert.ok(meta)
assert.equal(subagentDisplayName(meta), '知识库助手')
assert.match(formatSubagentTraceSummary(meta), /知识库助手/)
assert.match(formatSubagentTraceSummary(meta), /search_knowledge_base/)
assert.equal(normalizeSubagentTraceMeta(null), undefined)

console.log('subagentTrace.test.ts passed')
