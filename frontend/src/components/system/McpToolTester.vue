<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import axios from '@/utils/axios'
import { copyToClipboard } from '@/utils/clipboard'
import { useToast } from '@/composables/useToast'
import { renderSafeMarkdownPreview } from '@/utils/safeMarkdown'
import hljs from 'highlight.js'
import {
  PlayIcon,
  XMarkIcon,
  BeakerIcon,
  DocumentDuplicateIcon,
  CheckIcon,
} from '@heroicons/vue/24/outline'

type ResultKind = 'json' | 'markdown' | 'text'

const props = defineProps<{
  tool: any,
  isOpen: boolean
}>()

const emit = defineEmits(['close'])
const { showToast } = useToast()

const loading = ref(false)
const result = ref<unknown>(null)
const error = ref<string | null>(null)
const args = ref<Record<string, any>>({})
const copied = ref(false)

const schema = computed(() => {
  try {
    return JSON.parse(props.tool.parameter_schema)
  } catch {
    return {}
  }
})

const properties = computed(() => schema.value.properties || {})
const requiredFields = computed(() => schema.value.required || [])

watch(() => props.tool, () => {
  args.value = {}
  result.value = null
  error.value = null
  copied.value = false
}, { immediate: true })

const normalizeResultText = (value: unknown): string => {
  if (value == null) return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const tryPrettyJson = (text: string): string | null => {
  const trimmed = text.trim()
  if (!trimmed || (trimmed[0] !== '{' && trimmed[0] !== '[')) return null
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2)
  } catch {
    return null
  }
}

const looksLikeMarkdown = (text: string): boolean => {
  const sample = text.trim()
  if (!sample || sample.length < 8) return false
  return /^(#{1,6}\s|\s*[-*+]\s|\s*\d+\.\s)/m.test(sample)
    || /```[\s\S]*```/.test(sample)
    || /\*\*[^*\n]+\*\*/.test(sample)
    || /^\|.+\|$/m.test(sample)
    || /^>\s+/m.test(sample)
}

const formattedResult = computed(() => {
  const source = error.value != null ? error.value : result.value
  if (source == null || source === '') return null

  const rawText = normalizeResultText(source)
  const prettyJson = tryPrettyJson(rawText)
  if (prettyJson != null) {
    let highlighted = ''
    try {
      highlighted = hljs.highlight(prettyJson, { language: 'json', ignoreIllegals: true }).value
    } catch {
      highlighted = ''
    }
    return {
      kind: 'json' as ResultKind,
      copyText: prettyJson,
      displayText: prettyJson,
      html: highlighted,
      label: 'JSON',
    }
  }

  if (!error.value && looksLikeMarkdown(rawText)) {
    return {
      kind: 'markdown' as ResultKind,
      copyText: rawText,
      displayText: rawText,
      html: renderSafeMarkdownPreview(rawText),
      label: 'Markdown',
    }
  }

  return {
    kind: 'text' as ResultKind,
    copyText: rawText,
    displayText: rawText,
    html: '',
    label: 'Text',
  }
})

const handleCopyResult = async () => {
  const payload = formattedResult.value
  if (!payload?.copyText) return
  const ok = await copyToClipboard(payload.copyText)
  if (!ok) {
    showToast('复制失败', 'error')
    return
  }
  copied.value = true
  showToast('已复制到剪贴板', 'success')
  window.setTimeout(() => {
    copied.value = false
  }, 1500)
}

const executeTool = async () => {
  loading.value = true
  result.value = null
  error.value = null
  copied.value = false

  try {
    const res = await axios.post(`/api/portal/mcp/tools/${props.tool.id}/execute`, {
      arguments: args.value
    })

    if (res.data.status === 'success') {
      result.value = res.data.result
    } else {
      error.value = res.data.message || '执行失败'
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 z-[70] flex justify-end">
    <!-- Backdrop -->
    <div class="absolute inset-0 bg-gray-900/20 backdrop-blur-sm transition-opacity" @click="emit('close')"></div>

    <!-- Drawer -->
    <div class="relative w-full max-w-md bg-white h-full shadow-2xl flex flex-col animate-slide-in-right">
      <div class="p-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <h3 class="text-sm font-bold text-gray-800 flex items-center">
          <BeakerIcon class="w-4 h-4 mr-2 text-primary" />
          工具测试台
        </h3>
        <button @click="emit('close')" class="p-1 text-gray-400 hover:text-gray-600 rounded-md">
          <XMarkIcon class="w-5 h-5" />
        </button>
      </div>

      <div class="p-6 border-b border-gray-100">
        <h2 class="text-lg font-bold text-gray-900 mb-1">{{ tool.tool_name }}</h2>
        <p class="text-xs text-gray-500 italic">{{ tool.tool_description || '暂无描述' }}</p>
      </div>

      <div class="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
        <!-- Input Form -->
        <div class="space-y-4">
          <h4 class="text-xs font-bold text-gray-500 uppercase tracking-wider">参数输入</h4>
          <div v-if="Object.keys(properties).length === 0" class="text-xs text-gray-400 italic">
            此工具无需参数
          </div>
          <div v-else class="space-y-3">
            <div v-for="(prop, key) in properties" :key="key">
              <label class="block text-xs font-medium text-gray-700 mb-1">
                {{ key }} <span v-if="requiredFields.includes(key)" class="text-red-500">*</span>
              </label>
              <input
                v-if="prop.type === 'string' || !prop.type"
                v-model="args[key]"
                class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
                :placeholder="prop.description"
              />
              <input
                v-else-if="prop.type === 'integer' || prop.type === 'number'"
                type="number"
                v-model.number="args[key]"
                class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                :placeholder="prop.description"
              />
              <label v-else-if="prop.type === 'boolean'" class="flex items-center space-x-2 cursor-pointer">
                <input type="checkbox" v-model="args[key]" class="w-4 h-4 text-primary border-gray-300 rounded focus:ring-primary" />
                <span class="text-xs text-gray-500">{{ prop.description || '启用' }}</span>
              </label>
              <p v-if="prop.description" class="text-[10px] text-gray-400 mt-1">{{ prop.description }}</p>
            </div>
          </div>
        </div>

        <!-- Result Area -->
        <div v-if="formattedResult" class="space-y-2 animate-fade-in">
          <h4 class="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
            执行结果
            <span
              v-if="error"
              class="text-[10px] text-red-500 bg-red-50 px-1.5 py-0.5 rounded normal-case tracking-normal"
            >Failed</span>
            <span
              v-else
              class="text-[10px] text-green-600 bg-green-50 px-1.5 py-0.5 rounded normal-case tracking-normal"
            >Success</span>
            <span
              class="text-[10px] px-1.5 py-0.5 rounded normal-case tracking-normal font-semibold"
              :class="error
                ? 'bg-red-50 text-red-500'
                : formattedResult.kind === 'json'
                  ? 'bg-emerald-50 text-emerald-700'
                  : formattedResult.kind === 'markdown'
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'bg-slate-100 text-slate-600'"
            >{{ formattedResult.label }}</span>
          </h4>

          <div
            class="group/result relative rounded-lg border overflow-hidden"
            :class="error
              ? 'bg-red-50 border-red-100'
              : formattedResult.kind === 'markdown'
                ? 'bg-white border-gray-200'
                : 'bg-slate-900 border-slate-800'"
          >
            <button
              type="button"
              class="absolute top-2 right-2 z-10 inline-flex items-center justify-center rounded-md border p-1.5 shadow-sm transition-all opacity-0 group-hover/result:opacity-100 focus:opacity-100"
              :class="error || formattedResult.kind === 'markdown'
                ? 'bg-white/95 border-gray-200 text-gray-500 hover:text-primary hover:bg-gray-50'
                : 'bg-slate-800/90 border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700'"
              title="复制结果"
              aria-label="复制结果"
              @click="handleCopyResult"
            >
              <CheckIcon v-if="copied" class="w-3.5 h-3.5 text-emerald-500" />
              <DocumentDuplicateIcon v-else class="w-3.5 h-3.5" />
            </button>

            <div
              v-if="formattedResult.kind === 'json' && formattedResult.html"
              class="mcp-result-json p-3 pr-10 text-xs font-mono leading-relaxed whitespace-pre overflow-x-auto max-h-[360px] overflow-y-auto custom-scrollbar"
              :class="error ? 'text-red-700' : 'text-slate-100'"
              v-html="formattedResult.html"
            />
            <div
              v-else-if="formattedResult.kind === 'markdown'"
              class="mcp-result-markdown p-3 pr-10 text-sm text-gray-800 leading-relaxed max-h-[360px] overflow-y-auto custom-scrollbar"
              v-html="formattedResult.html"
            />
            <pre
              v-else
              class="p-3 pr-10 text-xs font-mono whitespace-pre-wrap break-words max-h-[360px] overflow-y-auto custom-scrollbar m-0"
              :class="error ? 'text-red-700' : 'text-green-400'"
            >{{ formattedResult.displayText }}</pre>
          </div>
        </div>
      </div>

      <div class="p-4 border-t border-gray-100 bg-gray-50 flex justify-end">
        <button
          @click="executeTool"
          :disabled="loading"
          class="w-full px-4 py-2 bg-primary text-white rounded-lg shadow-lg shadow-primary/20 hover:bg-primary-dark transition-all flex justify-center items-center font-bold text-sm disabled:opacity-70 disabled:cursor-not-allowed"
        >
          <svg v-if="loading" class="animate-spin h-4 w-4 mr-2 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <PlayIcon v-else class="w-4 h-4 mr-2" />
          运行测试
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-slide-in-right { animation: slideInRight 0.3s ease-out; }
@keyframes slideInRight { from { transform: translateX(100%); } to { transform: translateX(0); } }

.mcp-result-json :deep(.hljs-attr) { color: #7dd3fc; }
.mcp-result-json :deep(.hljs-string) { color: #86efac; }
.mcp-result-json :deep(.hljs-number) { color: #fcd34d; }
.mcp-result-json :deep(.hljs-literal) { color: #f9a8d4; }
.mcp-result-json :deep(.hljs-punctuation) { color: #cbd5e1; }

.mcp-result-markdown :deep(p) { margin: 0 0 0.65em; }
.mcp-result-markdown :deep(p:last-child) { margin-bottom: 0; }
.mcp-result-markdown :deep(ul),
.mcp-result-markdown :deep(ol) { margin: 0.4em 0 0.65em; padding-left: 1.25rem; }
.mcp-result-markdown :deep(li) { margin: 0.15em 0; }
.mcp-result-markdown :deep(code) {
  font-size: 0.75rem;
  background: #f3f4f6;
  border-radius: 0.25rem;
  padding: 0.1rem 0.3rem;
}
.mcp-result-markdown :deep(pre) {
  margin: 0.5em 0;
  padding: 0.75rem;
  border-radius: 0.5rem;
  background: #0f172a;
  color: #e2e8f0;
  overflow-x: auto;
}
.mcp-result-markdown :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}
.mcp-result-markdown :deep(a) { color: #2563eb; text-decoration: underline; }
.mcp-result-markdown :deep(h1),
.mcp-result-markdown :deep(h2),
.mcp-result-markdown :deep(h3),
.mcp-result-markdown :deep(h4) {
  font-weight: 700;
  margin: 0.75em 0 0.4em;
  line-height: 1.3;
}
.mcp-result-markdown :deep(blockquote) {
  margin: 0.5em 0;
  padding-left: 0.75rem;
  border-left: 3px solid #cbd5e1;
  color: #64748b;
}
.mcp-result-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5em 0;
  font-size: 0.75rem;
}
.mcp-result-markdown :deep(th),
.mcp-result-markdown :deep(td) {
  border: 1px solid #e5e7eb;
  padding: 0.35rem 0.5rem;
  text-align: left;
}
.mcp-result-markdown :deep(th) { background: #f9fafb; font-weight: 600; }
</style>
