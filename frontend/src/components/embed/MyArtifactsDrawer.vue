<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { artifactApi, type ArtifactListItem } from '@/api/artifact'
import { resolveGeneratedFileHref } from '@/utils/generatedFileUrl'
import { resolveFileTypeVisual } from '@/utils/fileTypeVisual'
import { useToast } from '@/composables/useToast'
import ReusableResultList from '@/components/embed/ReusableResultList.vue'
import type { ReusableResultListItem } from '@/api/artifact'

const modelValue = defineModel<boolean>({ default: false })

const props = withDefaults(defineProps<{
  conversationId?: string | null
  initialTab?: 'files' | 'reusable'
  selectedResultId?: string | null
  focusedResultId?: string | null
}>(), {
  conversationId: null,
  initialTab: 'files',
  selectedResultId: null,
  focusedResultId: null,
})

const emit = defineEmits<{
  'select-reusable-result': [result: ReusableResultListItem]
}>()

const { showToast } = useToast()

const ARTIFACT_TYPES = [
  { value: '', label: '全部' },
  { value: 'word', label: 'Word' },
  { value: 'excel', label: 'Excel' },
  { value: 'export', label: '导出' },
]
const PAGE_SIZE = 50

const items = ref<ArtifactListItem[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const activeType = ref('')
const activeTab = ref<'files' | 'reusable'>('files')
const bodyRef = ref<HTMLElement | null>(null)

const typeLabel = (t: string) =>
  ARTIFACT_TYPES.find((x) => x.value === t)?.label || t || '未知'
const formatSize = (size: number) => {
  if (!size) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let v = size
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v >= 10 ? v.toFixed(0) : v.toFixed(1)} ${units[i]}`
}
const formatTime = (iso?: string | null) => {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const fileVisuals = computed<Record<string, ReturnType<typeof resolveFileTypeVisual>>>(() => {
  const map: Record<string, ReturnType<typeof resolveFileTypeVisual>> = {}
  for (const it of items.value) {
    map[it.id] = resolveFileTypeVisual(it.filename)
  }
  return map
})

const isMobile = ref(
  typeof window !== 'undefined' && window.matchMedia('(max-width: 639px)').matches,
)

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await artifactApi.list({
      page: page.value,
      page_size: PAGE_SIZE,
      artifact_type: activeType.value || undefined,
    })
    const data = res.data?.data
    items.value = data?.items ?? []
    total.value = data?.total ?? 0
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '加载产出物失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

const refresh = () => {
  page.value = 1
  void load()
}

const changeType = (val: string) => {
  activeType.value = val
  refresh()
}

const scrollHandler = () => {
  const el = bodyRef.value
  if (!el || loading.value) return
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 40) {
    if (items.value.length < total.value) {
      page.value += 1
      void loadMore()
    }
  }
}

const loadMore = async () => {
  loading.value = true
  try {
    const res = await artifactApi.list({
      page: page.value,
      page_size: PAGE_SIZE,
      artifact_type: activeType.value || undefined,
    })
    const data = res.data?.data
    const more = data?.items ?? []
    items.value = items.value.concat(more)
    total.value = data?.total ?? total.value
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '加载更多失败', 'error')
  } finally {
    loading.value = false
  }
}

const openArtifact = (it: ArtifactListItem) => {
  if (!it.download_url) {
    showToast('该产出物缺少下载地址', 'warning')
    return
  }
  const href = resolveGeneratedFileHref(it.download_url)
  window.open(href, '_blank', 'noopener,noreferrer')
}

const closeDrawer = () => {
  modelValue.value = false
}

const keyHandler = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && modelValue.value) closeDrawer()
}

watch(modelValue, (open) => {
  if (open) {
    activeTab.value = props.initialTab
    if (activeTab.value === 'files') refresh()
  }
})

watch(() => props.initialTab, (tab) => {
  if (modelValue.value) activeTab.value = tab
})

const selectReusableResult = (result: ReusableResultListItem) => {
  emit('select-reusable-result', result)
}

onMounted(() => {
  window.addEventListener('keydown', keyHandler)
})

onUnmounted(() => {
  window.removeEventListener('keydown', keyHandler)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-show="modelValue"
      class="fixed inset-0 z-[125] overflow-hidden"
    >
      <transition
        enter-active-class="ease-out duration-300"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="ease-in duration-200"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-show="modelValue"
          class="absolute inset-0 bg-gray-500/30 backdrop-blur-xs transition-opacity"
          @click="closeDrawer"
        />
      </transition>

      <transition
        enter-active-class="ease-out duration-300"
        enter-from-class="translate-x-full"
        enter-to-class="translate-x-0"
        leave-active-class="ease-in duration-200"
        leave-from-class="translate-x-0"
        leave-to-class="translate-x-full"
      >
        <div
          v-show="modelValue"
          :class="[
            isMobile
              ? 'absolute inset-0 flex w-full flex-col overflow-hidden'
              : 'absolute inset-y-0 right-0 pl-0 sm:pl-10 max-w-full flex',
          ]"
        >
          <div
            :class="[
              'flex flex-col bg-white dark:bg-gray-900 shadow-2xl border-gray-200 dark:border-gray-700 pointer-events-auto min-w-0',
              isMobile ? 'w-full h-full border-0' : 'w-96 sm:w-[28rem] max-w-full h-full border-l',
            ]"
          >
            <!-- Header -->
            <div class="px-4 py-3 border-b border-gray-100 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50 flex items-center justify-between gap-3 flex-shrink-0">
              <div class="flex items-center gap-2 min-w-0">
                <svg class="h-5 w-5 text-gray-500 dark:text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <h3 class="text-sm font-black text-gray-800 dark:text-gray-100 truncate">{{ activeTab === 'files' ? '我的产出' : '可复用结果' }}</h3>
                <span v-if="activeTab === 'files' && total > 0" class="text-[10px] text-gray-400 font-mono bg-white dark:bg-gray-700 px-1.5 py-0.5 rounded border border-gray-100 dark:border-gray-600 flex-shrink-0">
                  {{ total }}
                </span>
              </div>
              <button
                type="button"
                class="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300 p-1.5 rounded-md hover:bg-gray-150 dark:hover:bg-gray-800 transition-colors"
                title="关闭 (Esc)"
                aria-label="关闭产出物"
                @click="closeDrawer"
              >
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <!-- Output tabs -->
            <div class="flex items-center gap-1 px-4 py-2 border-b border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-900/40 flex-shrink-0 overflow-x-auto no-scrollbar">
              <button
                type="button"
                class="px-2.5 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors"
                :class="activeTab === 'files' ? 'bg-primary/10 text-primary' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'"
                @click="activeTab = 'files'; refresh()"
              >
                文件产物
              </button>
              <button
                type="button"
                class="px-2.5 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors"
                :class="activeTab === 'reusable' ? 'bg-primary/10 text-primary' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'"
                @click="activeTab = 'reusable'"
              >
                可复用结果
              </button>
            </div>

            <!-- File type filter -->
            <div v-if="activeTab === 'files'" class="flex items-center gap-1 px-4 py-2 border-b border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-900/40 flex-shrink-0 overflow-x-auto no-scrollbar">
              <button
                v-for="t in ARTIFACT_TYPES"
                :key="t.value"
                type="button"
                class="px-2.5 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors"
                :class="
                  activeType === t.value
                    ? 'bg-primary/10 text-primary'
                    : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                "
                @click="changeType(t.value)"
              >
                {{ t.label }}
              </button>
            </div>

            <!-- Body -->
            <div
              ref="bodyRef"
              class="flex-1 overflow-y-auto overscroll-y-contain p-3 sm:p-4 bg-white dark:bg-gray-900/60 min-h-0 touch-pan-y"
              @scroll.passive="scrollHandler"
            >
              <ReusableResultList
                v-if="activeTab === 'reusable'"
                :conversation-id="props.conversationId || ''"
                :selected-result-id="props.selectedResultId"
                :focused-result-id="props.focusedResultId"
                @select="selectReusableResult"
              />

              <template v-else>
              <!-- Loading -->
              <div v-if="loading && items.length === 0" class="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
                <svg class="h-6 w-6 text-primary animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span class="text-xs font-medium">加载中...</span>
              </div>

              <!-- Error -->
              <div v-else-if="error && items.length === 0" class="flex flex-col items-center justify-center py-16 text-gray-500 dark:text-gray-400 gap-3">
                <svg class="h-8 w-8 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="text-xs font-medium text-center">{{ error }}</span>
                <button
                  type="button"
                  class="text-xs font-semibold text-primary hover:underline"
                  @click="refresh"
                >
                  重试
                </button>
              </div>

              <!-- Empty -->
              <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
                <svg class="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                </svg>
                <span class="text-xs font-medium">暂无 AI 产出物</span>
              </div>

              <!-- List -->
              <ul v-else class="flex flex-col gap-2">
                <li v-for="it in items" :key="it.id">
                  <button
                    type="button"
                    class="w-full flex items-start gap-3 rounded-xl p-3 text-left transition-colors border border-transparent hover:bg-gray-50 dark:hover:bg-gray-800/60 hover:border-gray-100 dark:hover:border-gray-700 group"
                    :title="`打开 ${it.filename}`"
                    @click="openArtifact(it)"
                  >
                    <span
                      :class="[
                        'flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center border mt-0.5 text-lg',
                        fileVisuals[it.id]?.iconBg || 'bg-gray-100 dark:bg-gray-800',
                      ]"
                    >
                      {{ fileVisuals[it.id]?.icon || '📎' }}
                    </span>
                    <span class="flex-1 min-w-0">
                      <span class="block text-sm font-semibold text-gray-800 dark:text-gray-100 truncate">
                        {{ it.filename }}
                      </span>
                      <span class="block text-[11px] text-gray-400 dark:text-gray-500 mt-0.5 flex items-center gap-1.5">
                        <span class="px-1 py-px rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-semibold">{{ typeLabel(it.artifact_type) }}</span>
                        <span>{{ formatSize(it.size) }}</span>
                        <span v-if="formatTime(it.created_at)">{{ formatTime(it.created_at) }}</span>
                        <svg class="h-3 w-3 text-gray-300 dark:text-gray-600 group-hover:text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </span>
                    </span>
                  </button>
                </li>
                <li v-if="loading" class="flex items-center justify-center py-4">
                  <svg class="h-5 w-5 text-primary animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </li>
              </ul>
              </template>
            </div>
          </div>
        </div>
      </transition>
    </div>
  </Teleport>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
