<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import {
  artifactApi,
  type ReusableResultListItem,
} from '@/api/artifact'

const props = withDefaults(defineProps<{
  conversationId: string
  selectedResultId?: string | null
  focusedResultId?: string | null
}>(), {
  selectedResultId: null,
  focusedResultId: null,
})

const emit = defineEmits<{
  select: [result: ReusableResultListItem]
}>()

const items = ref<ReusableResultListItem[]>([])
const loading = ref(false)
const error = ref('')

const formatTime = (iso?: string | null) => {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const resultTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    data: '数据',
    knowledge: '知识',
    web: '网页',
    file: '文件',
    code: '代码',
    generic: '通用',
  }
  return labels[type] || type || '通用'
}

const load = async () => {
  if (!props.conversationId) {
    items.value = []
    return
  }
  loading.value = true
  error.value = ''
  try {
    const response = await artifactApi.reusableResults(props.conversationId)
    items.value = response.data?.data?.items || []
    await nextTick()
    focusSelectedResult()
  } catch (err: any) {
    items.value = []
    error.value = err?.response?.data?.detail || '加载可复用结果失败'
  } finally {
    loading.value = false
  }
}

const focusSelectedResult = () => {
  if (!props.focusedResultId) return
  const element = document.querySelector<HTMLElement>(
    `[data-reusable-result-id="${CSS.escape(props.focusedResultId)}"]`,
  )
  element?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
}

const selectResult = (item: ReusableResultListItem) => {
  emit('select', item)
}

watch(() => props.conversationId, () => void load())
watch(() => props.focusedResultId, () => void nextTick(focusSelectedResult))
onMounted(() => void load())
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between gap-2">
      <div>
        <h4 class="text-sm font-bold text-gray-800 dark:text-gray-100">可复用结果</h4>
        <p class="mt-0.5 text-[11px] text-gray-400 dark:text-gray-500">优先读取已有结果，减少重复查询</p>
      </div>
      <button
        type="button"
        class="rounded-md px-2 py-1 text-[11px] font-semibold text-primary hover:bg-primary/10 disabled:opacity-50"
        :disabled="loading"
        @click="load"
      >
        {{ loading ? '加载中…' : '刷新' }}
      </button>
    </div>

    <div v-if="loading && items.length === 0" class="flex items-center justify-center gap-2 py-12 text-xs text-gray-400">
      <svg class="h-4 w-4 animate-spin text-primary" fill="none" viewBox="0 0 24 24" aria-hidden="true">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <span>加载中…</span>
    </div>

    <div v-else-if="error" class="rounded-xl border border-amber-100 bg-amber-50 px-3 py-4 text-center text-xs text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-300">
      <p>{{ error }}</p>
      <button type="button" class="mt-2 font-semibold underline" @click="load">重试</button>
    </div>

    <div v-else-if="items.length === 0" class="rounded-xl border border-dashed border-gray-200 px-3 py-10 text-center text-xs text-gray-400 dark:border-gray-700">
      本会话暂无可复用结果
    </div>

    <ul v-else class="flex flex-col gap-2">
      <li
        v-for="item in items"
        :key="item.result_id"
        :data-reusable-result-id="item.result_id"
      >
        <button
          type="button"
          class="w-full rounded-xl border p-3 text-left transition-colors"
          :class="[
            item.result_id === props.selectedResultId
              ? 'border-primary bg-primary/5 dark:bg-primary/10'
              : item.result_id === props.focusedResultId
                ? 'border-primary/40 bg-primary/[0.03]'
                : 'border-gray-100 hover:border-primary/30 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800/60',
          ]"
          :aria-pressed="item.result_id === props.selectedResultId"
          @click="selectResult(item)"
        >
          <span class="flex items-start gap-3">
            <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-base text-primary">↗</span>
            <span class="min-w-0 flex-1">
              <span class="flex items-center gap-1.5">
                <span class="truncate text-sm font-semibold text-gray-800 dark:text-gray-100">{{ item.origin_name || '未知来源' }}</span>
                <span v-if="item.is_current" class="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">当前</span>
              </span>
              <span class="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-gray-400 dark:text-gray-500">
                <span class="rounded bg-gray-100 px-1.5 py-0.5 font-semibold dark:bg-gray-800">{{ resultTypeLabel(item.result_type) }}</span>
                <span v-if="formatTime(item.created_at)">{{ formatTime(item.created_at) }}</span>
                <span v-if="item.expires_at">· {{ formatTime(item.expires_at) }} 过期</span>
              </span>
              <span v-if="item.text_excerpt" class="mt-2 line-clamp-3 block whitespace-pre-wrap break-words text-xs leading-5 text-gray-600 dark:text-gray-300">{{ item.text_excerpt }}</span>
              <span v-if="item.structured_preview?.row_count !== undefined || item.structured_preview?.item_count !== undefined" class="mt-2 block text-[10px] text-gray-400 dark:text-gray-500">
                <template v-if="item.structured_preview?.row_count !== undefined">{{ item.structured_preview.row_count }} 行</template>
                <template v-else>{{ item.structured_preview?.item_count }} 项</template>
                <template v-if="item.structured_preview?.columns?.length"> · {{ item.structured_preview.columns.length }} 列</template>
              </span>
              <span class="mt-2 block text-[11px] font-semibold" :class="item.result_id === props.selectedResultId ? 'text-primary' : 'text-gray-500 dark:text-gray-400'">
                {{ item.result_id === props.selectedResultId ? '已选择，用于下一轮分析' : '选择用于下一轮' }}
              </span>
            </span>
          </span>
        </button>
      </li>
    </ul>
  </div>
</template>
