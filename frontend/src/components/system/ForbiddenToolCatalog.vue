<template>
  <div class="space-y-3">
    <!-- 大组 1：内置高危工具（可折叠，子组按 category 分组） -->
    <div v-show="showBuiltinSection" class="border border-gray-150 rounded-xl p-3 bg-white">
      <div class="flex items-center justify-between gap-3 mb-2 select-none">
        <button
          type="button"
          @click="toggleCollapse(GROUP_BUILTIN_KEY)"
          :disabled="isSearching"
          :title="isSearching ? '搜索状态下分组自动展开，清空搜索后可折叠' : ''"
          :class="isSearching ? 'cursor-default' : ''"
          class="flex items-center gap-1.5 min-w-0 flex-1 text-left"
        >
          <svg class="w-3.5 h-3.5 text-gray-400 transition-transform shrink-0" :class="{ 'rotate-90': isExpanded(GROUP_BUILTIN_KEY) }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
          <span class="w-1.5 h-1.5 bg-red-500 rounded-full"></span>
          <span class="text-xs font-bold text-gray-700 truncate">选择要禁用的工具（全局拉黑）</span>
          <span class="text-[10px] text-gray-400 font-normal shrink-0">({{ selectedCountOf(builtinVisibleCandidates) }}/{{ builtinVisibleCandidates.length }})</span>
        </button>
        <div class="flex items-center gap-2 shrink-0">
          <button
            v-if="!disabled"
            type="button"
            :disabled="!builtinVisibleCandidates.length"
            @click.stop="toggleSelection(builtinVisibleCandidates, !isAllSelected(builtinVisibleCandidates))"
            class="text-[10px] font-bold text-red-600 hover:text-red-800 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {{ isAllSelected(builtinVisibleCandidates) ? '取消全选' : '全选' }}
          </button>
          <input
            v-model="searchQuery"
            type="search"
            placeholder="搜索工具名..."
            class="text-[10px] border border-gray-200 rounded px-2 py-0.5 w-[140px] focus:outline-none focus:border-indigo-500"
          />
        </div>
      </div>
      <p v-if="loading" class="text-[10px] text-gray-400">正在加载可禁用工具目录…</p>
      <p v-else-if="loadError" class="text-[10px] text-red-500">{{ loadError }}</p>
      <div v-else v-show="isExpanded(GROUP_BUILTIN_KEY)" class="space-y-2">
        <div
          v-for="sub in visibleBuiltinGroups"
          :key="sub.key"
          class="rounded-lg border border-gray-200 overflow-hidden"
        >
          <div class="flex items-center justify-between py-1.5 px-2.5 bg-gray-50 border-b border-gray-100">
            <button
              type="button"
              @click="toggleCollapse(sub.key)"
              :disabled="isSearching"
              :title="isSearching ? '搜索状态下分组自动展开，清空搜索后可折叠' : ''"
              :class="isSearching ? 'cursor-default' : ''"
              class="flex items-center gap-2 min-w-0 flex-1 text-left"
            >
              <svg class="w-3.5 h-3.5 text-gray-400 transition-transform shrink-0" :class="{ 'rotate-90': isExpanded(sub.key) }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
              <span class="text-[11px] font-bold text-gray-700 truncate">{{ sub.label }}</span>
              <span class="text-[10px] text-gray-400 shrink-0">({{ selectedCountOf(sub.candidates) }}/{{ sub.candidates.length }})</span>
            </button>
            <button
              v-if="!disabled"
              type="button"
              @click.stop="toggleSelection(sub.candidates, !isAllSelected(sub.candidates))"
              class="text-[10px] font-bold text-red-600 hover:text-red-800 ml-2 shrink-0"
            >
              {{ isAllSelected(sub.candidates) ? '取消全选' : '全选' }}
            </button>
          </div>
          <div v-show="isExpanded(sub.key)" class="grid grid-cols-1 sm:grid-cols-2 gap-2 p-2">
            <label
              v-for="candidate in sub.candidates"
              :key="candidate.id"
              class="flex items-start p-2 rounded border bg-white transition-colors"
              :class="disabled ? 'opacity-60 cursor-not-allowed' : 'hover:bg-gray-50 cursor-pointer'"
            >
              <input
                type="checkbox"
                :checked="isCandidateSelected(candidate)"
                :disabled="disabled"
                class="mt-1 h-4 w-4 rounded text-red-600 focus:ring-red-500"
                @change="toggleCandidate(candidate, ($event.target as HTMLInputElement).checked)"
              />
              <div class="ml-2 min-w-0">
                <p class="text-xs sm:text-sm font-bold text-gray-900 truncate">{{ candidate.label }}</p>
                <p class="text-[9px] text-gray-400 truncate">{{ candidate.description }}</p>
                <p v-if="candidate.aliases.length > 1" class="text-[9px] text-red-400 truncate">
                  同时拦截：{{ candidate.aliases.filter((alias) => alias !== candidate.id).join('、') }}
                </p>
              </div>
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- 大组 2：自定义 API 与 MCP 扩展工具（可折叠；无内滚动，长度交给子组折叠） -->
    <div v-show="showDynamicSection" class="border border-gray-150 rounded-xl p-3 bg-white">
      <div class="flex items-center justify-between gap-3 mb-2 select-none">
        <button
          type="button"
          @click="toggleCollapse(GROUP_DYNAMIC_KEY)"
          :disabled="isSearching"
          :title="isSearching ? '搜索状态下分组自动展开，清空搜索后可折叠' : ''"
          :class="isSearching ? 'cursor-default' : ''"
          class="flex items-center gap-1.5 min-w-0 flex-1 text-left"
        >
          <svg class="w-3.5 h-3.5 text-indigo-400 transition-transform shrink-0" :class="{ 'rotate-90': isExpanded(GROUP_DYNAMIC_KEY) }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
          <span class="w-1.5 h-1.5 bg-indigo-500 rounded-full"></span>
          <span class="text-xs font-bold text-gray-700 truncate">自定义 API 与 MCP 扩展工具禁用</span>
          <span class="text-[10px] text-gray-400 font-normal shrink-0">({{ selectedCountOf(dynamicVisibleCandidates) }}/{{ dynamicVisibleCandidates.length }})</span>
        </button>
        <button
          v-if="!disabled"
          type="button"
          :disabled="!dynamicVisibleCandidates.length"
          @click.stop="toggleSelection(dynamicVisibleCandidates, !isAllSelected(dynamicVisibleCandidates))"
          class="text-[10px] font-bold text-indigo-600 hover:text-indigo-800 shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {{ isAllSelected(dynamicVisibleCandidates) ? '取消全选' : '全选' }}
        </button>
      </div>
      <div v-show="isExpanded(GROUP_DYNAMIC_KEY)" class="space-y-2">
        <div
          v-for="sub in visibleDynamicGroups"
          :key="sub.key"
          class="rounded-lg border border-indigo-100 overflow-hidden"
        >
          <div class="flex items-center justify-between py-1.5 px-2.5 bg-indigo-50/60 border-b border-indigo-100/50">
            <button
              type="button"
              @click="toggleCollapse(sub.key)"
              :disabled="isSearching"
              :title="isSearching ? '搜索状态下分组自动展开，清空搜索后可折叠' : ''"
              :class="isSearching ? 'cursor-default' : ''"
              class="flex items-center gap-2 min-w-0 flex-1 text-left"
            >
              <svg class="w-3.5 h-3.5 text-indigo-400 transition-transform shrink-0" :class="{ 'rotate-90': isExpanded(sub.key) }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
              <span class="text-[11px] font-bold text-indigo-700 truncate">{{ sub.label }}</span>
              <span class="text-[10px] text-indigo-400 shrink-0">({{ selectedCountOf(sub.candidates) }}/{{ sub.candidates.length }})</span>
            </button>
            <button
              v-if="!disabled"
              type="button"
              @click.stop="toggleSelection(sub.candidates, !isAllSelected(sub.candidates))"
              class="text-[10px] font-bold text-indigo-600 hover:text-indigo-800 ml-2 shrink-0"
            >
              {{ isAllSelected(sub.candidates) ? '取消全选' : '全选' }}
            </button>
          </div>
          <div v-show="isExpanded(sub.key)" class="grid grid-cols-1 sm:grid-cols-2 gap-1.5 p-2">
            <label
              v-for="candidate in sub.candidates"
              :key="candidate.id"
              class="flex items-center p-1.5 rounded border bg-white hover:bg-gray-50 transition-colors cursor-pointer text-xs"
              :class="disabled ? 'opacity-60 cursor-not-allowed' : ''"
            >
              <input
                type="checkbox"
                :checked="isCandidateSelected(candidate)"
                :disabled="disabled"
                class="h-3.5 w-3.5 rounded text-indigo-600 focus:ring-indigo-500"
                @change="toggleCandidate(candidate, ($event.target as HTMLInputElement).checked)"
              />
              <div class="ml-1.5 min-w-0 flex-1">
                <p class="font-bold text-gray-900 truncate text-[11px] leading-tight">{{ candidate.label }}</p>
                <p class="text-[9px] text-gray-400 truncate mt-0.5">{{ candidate.description }}</p>
              </div>
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- 历史遗留：已禁用但已不在目录中的工具，必须仍可见、可解除（不被搜索过滤） -->
    <div v-if="orphanIds.length" class="border border-amber-200 rounded-xl p-3 bg-amber-50/40">
      <h4 class="text-xs font-bold text-amber-700 mb-1.5 flex items-center gap-1.5 select-none">
        <span class="w-1.5 h-1.5 bg-amber-500 rounded-full"></span>
        其他已禁用项（历史）
      </h4>
      <p class="text-[10px] text-amber-600 mb-2">这些工具已不在当前目录中（例如 MCP 工具已下架），取消勾选即可解除禁用。</p>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
        <label
          v-for="orphanId in orphanIds"
          :key="orphanId"
          class="flex items-center p-1.5 rounded border bg-white hover:bg-gray-50 transition-colors cursor-pointer text-xs"
        >
          <input
            type="checkbox"
            checked
            :disabled="disabled"
            class="h-3.5 w-3.5 rounded text-amber-600 focus:ring-amber-500"
            @change="toggleOrphan(orphanId, ($event.target as HTMLInputElement).checked)"
          />
          <p class="ml-1.5 min-w-0 flex-1 font-mono text-[11px] text-gray-700 truncate">{{ orphanId }}</p>
        </label>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import {
  applyGroupSelection,
  filterSubGroups,
  groupCandidates,
  groupSelectedCount,
  type ForbiddenToolCandidate,
  type ForbiddenToolSubGroup,
} from '../../utils/forbiddenToolGroups'

const props = withDefaults(defineProps<{ modelValue: string[]; disabled?: boolean }>(), {
  disabled: false,
})

const emit = defineEmits<{ (e: 'update:modelValue', value: string[]): void }>()

/** 大组折叠键；子组折叠键直接复用后端给的 group_key。 */
const GROUP_BUILTIN_KEY = 'group:builtin'
const GROUP_DYNAMIC_KEY = 'group:dynamic'

const candidates = ref<ForbiddenToolCandidate[]>([])
const loading = ref(false)
const loadError = ref('')
const searchQuery = ref('')

/** 折叠集合：空集 = 默认全展开；只在本组件存活期间记忆，不持久化。 */
const collapsedKeys = ref<Set<string>>(new Set())

const isSearching = computed(() => searchQuery.value.trim().length > 0)

const toggleCollapse = (key: string) => {
  const next = new Set(collapsedKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsedKeys.value = next
}

/** 搜索期间强制展开：只读覆盖，不写回 collapsedKeys，清空搜索即回到原状态。 */
const isExpanded = (key: string) => isSearching.value || !collapsedKeys.value.has(key)

const selectedIds = computed(() => new Set((props.modelValue || []).map((id) => String(id))))
const catalogIds = computed(() => new Set(candidates.value.map((candidate) => candidate.id)))

// 大组划分沿用既有 category 判据：旧响应没有 group_key 时也能正确落组
const builtinCandidates = computed(() =>
  candidates.value.filter((candidate) => candidate.category !== 'api' && candidate.category !== 'mcp'),
)
const dynamicCandidates = computed(() =>
  candidates.value.filter((candidate) => candidate.category === 'api' || candidate.category === 'mcp'),
)

const builtinGroups = computed(() => groupCandidates(builtinCandidates.value))
const dynamicGroups = computed(() => groupCandidates(dynamicCandidates.value))

// 搜索只决定可见子组，不写回折叠集合
const visibleBuiltinGroups = computed(() => filterSubGroups(builtinGroups.value, searchQuery.value))
const visibleDynamicGroups = computed(() => filterSubGroups(dynamicGroups.value, searchQuery.value))

const builtinVisibleCandidates = computed(() =>
  visibleBuiltinGroups.value.flatMap((sub) => sub.candidates),
)
const dynamicVisibleCandidates = computed(() =>
  visibleDynamicGroups.value.flatMap((sub) => sub.candidates),
)

/** 计数与全选判定都委托纯函数：这里只把候选列表包成"组"的形状。 */
const asGroup = (key: string, list: ForbiddenToolCandidate[]): ForbiddenToolSubGroup => ({
  key,
  label: key,
  candidates: list,
})
const selectedCountOf = (list: ForbiddenToolCandidate[]) =>
  groupSelectedCount(asGroup('__selection__', list), selectedIds.value)
const isAllSelected = (list: ForbiddenToolCandidate[]) =>
  list.length > 0 && selectedCountOf(list) === list.length
const isCandidateSelected = (candidate: ForbiddenToolCandidate) => selectedCountOf([candidate]) > 0

const toggleSelection = (list: ForbiddenToolCandidate[], checked: boolean) => {
  emit('update:modelValue', applyGroupSelection(props.modelValue || [], list, checked))
}

/** 单卡片勾选与组级全选同语义：写入 / 移除该候选的全部 aliases。 */
const toggleCandidate = (candidate: ForbiddenToolCandidate, checked: boolean) => {
  toggleSelection([candidate], checked)
}

/** 已选中但已不在目录里的工具：必须可见、可解除。 */
const orphanIds = computed(() =>
  Array.from(selectedIds.value).filter((id) => !catalogIds.value.has(id)),
)

const toggleOrphan = (id: string, checked: boolean) => {
  const next = new Set(selectedIds.value)
  if (checked) next.add(id)
  else next.delete(id)
  emit('update:modelValue', Array.from(next))
}

/** 大组 1 原来恒显示；现在搜索无命中时整组隐藏（加载中 / 失败仍要显示提示）。 */
const showBuiltinSection = computed(() =>
  !isSearching.value
  || loading.value
  || Boolean(loadError.value)
  || visibleBuiltinGroups.value.length > 0,
)
const showDynamicSection = computed(() => visibleDynamicGroups.value.length > 0)

const fetchCatalog = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await axios.get('/api/portal/tools/forbidden-catalog')
    candidates.value = Array.isArray(response.data?.candidates) ? response.data.candidates : []
  } catch (error) {
    loadError.value = '可禁用工具目录加载失败，请刷新页面重试。'
  } finally {
    loading.value = false
  }
}

onMounted(fetchCatalog)
</script>
