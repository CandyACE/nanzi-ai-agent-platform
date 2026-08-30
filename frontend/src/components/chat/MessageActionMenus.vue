<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue"

const props = withDefaults(defineProps<{
  mode?: "data" | "regenerate" | "more" | "both"
  hasDataOutput?: boolean
  showDataOnMobile?: boolean
  canExport?: boolean
  hasTrace?: boolean
  reusableCount?: number | null
  artifactCount?: number
  canRegenerate?: boolean
  hasTokenStats?: boolean
  canSaveReport?: boolean
}>(), {
  mode: "both",
  hasDataOutput: false,
  showDataOnMobile: false,
  canExport: false,
  hasTrace: false,
  reusableCount: null,
  artifactCount: 0,
  canRegenerate: false,
  hasTokenStats: false,
  canSaveReport: false,
})

const emit = defineEmits<{
  exportData: []
  openReusableResults: []
  openArtifacts: []
  regenerate: []
  openTrace: []
  openStats: []
  saveReport: []
}>()

const openMenu = ref<"data" | "more" | null>(null)
const root = ref<HTMLElement | null>(null)

const hasDataFile = computed(() => Boolean(
  props.hasDataOutput || (props.reusableCount && props.reusableCount > 0) || props.artifactCount > 0,
))
const hasMore = computed(() => Boolean(
  props.canExport || props.hasTrace || props.hasTokenStats || props.canSaveReport || (props.showDataOnMobile && hasDataFile.value),
))
const hasMobileDataMenu = computed(() => Boolean(props.showDataOnMobile && (hasDataFile.value || props.canExport)))

const closeOnOutside = (event: PointerEvent) => {
  if (openMenu.value && !root.value?.contains(event.target as Node)) openMenu.value = null
}
const closeOnEscape = (event: KeyboardEvent) => {
  if (event.key === "Escape") openMenu.value = null
}
const toggle = (menu: "data" | "more") => {
  openMenu.value = openMenu.value === menu ? null : menu
}
const run = (action: () => void) => {
  openMenu.value = null
  action()
}

onMounted(() => {
  document.addEventListener("pointerdown", closeOnOutside)
  document.addEventListener("keydown", closeOnEscape)
})
onUnmounted(() => {
  document.removeEventListener("pointerdown", closeOnOutside)
  document.removeEventListener("keydown", closeOnEscape)
})
</script>

<template>
  <div ref="root" class="flex items-center gap-1">
    <div v-if="(mode === 'data' || mode === 'both') && hasDataFile" class="relative">
      <button
        type="button"
        class="flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
        :class="{ 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200': openMenu === 'data' }"
        :aria-expanded="openMenu === 'data'"
        aria-haspopup="menu"
        title="查看本条消息关联的数据和文件"
        @click="toggle('data')"
      >
        <span aria-hidden="true">▤</span>
        <span>数据 / 文件</span>
        <span v-if="reusableCount && reusableCount > 0" class="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white">数据 {{ reusableCount }}</span>
        <span v-if="artifactCount > 0" class="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white">文件 {{ artifactCount }}</span>
        <span class="text-[9px]">⌄</span>
      </button>
      <div v-if="openMenu === 'data'" class="absolute bottom-full left-0 z-50 mb-2 w-52 rounded-xl border border-gray-200 bg-white p-1.5 shadow-xl dark:border-gray-700 dark:bg-gray-900" role="menu">
        <button v-if="reusableCount && reusableCount > 0" type="button" class="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800" role="menuitem" @click="run(() => emit('openReusableResults'))">
          <span>▤ 查看可复用结果</span><span class="text-[10px] text-gray-400">{{ reusableCount }} 条</span>
        </button>
        <button v-if="artifactCount > 0" type="button" class="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800" role="menuitem" @click="run(() => emit('openArtifacts'))">
          <span>▣ 查看文件产物</span><span class="text-[10px] text-gray-400">{{ artifactCount }} 个</span>
        </button>
      </div>
    </div>

    <template v-if="mode === 'regenerate' || mode === 'both'">
      <button
        v-if="canRegenerate"
        type="button"
        class="flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
        title="重新生成"
        @click="run(() => emit('regenerate'))"
      >
        <span aria-hidden="true">↻</span>
        <span class="hidden sm:inline">重新生成</span>
      </button>
    </template>
    <template v-if="mode === 'more' || mode === 'both'">
      <div v-if="hasMore" class="relative">
        <button type="button" class="flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200" :class="{ 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200': openMenu === 'more' }" :aria-expanded="openMenu === 'more'" aria-haspopup="menu" title="更多操作" @click="toggle('more')">⋯ 更多</button>
        <div v-if="openMenu === 'more'" class="absolute bottom-full right-0 z-50 mb-2 w-48 rounded-xl border border-gray-200 bg-white p-1.5 shadow-xl dark:border-gray-700 dark:bg-gray-900" role="menu">
          <div v-if="hasMobileDataMenu" class="sm:hidden">
            <div v-if="hasDataFile" class="flex items-center gap-1 px-2.5 py-2 text-[10px] font-semibold text-gray-400 dark:text-gray-500">
              <span>▤ 数据 / 文件</span>
              <span v-if="reusableCount && reusableCount > 0" class="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white">数据 {{ reusableCount }}</span>
              <span v-if="artifactCount > 0" class="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white">文件 {{ artifactCount }}</span>
            </div>
            <button v-if="reusableCount && reusableCount > 0" type="button" class="menu-item" role="menuitem" @click="run(() => emit('openReusableResults'))">▤ 查看可复用结果</button>
            <button v-if="canExport" type="button" class="menu-item" role="menuitem" @click="run(() => emit('exportData'))">↓ 导出数据（Excel）</button>
            <button v-if="artifactCount > 0" type="button" class="menu-item" role="menuitem" @click="run(() => emit('openArtifacts'))">▣ 查看文件产物</button>
            <div v-if="hasTrace || hasTokenStats || canSaveReport" class="my-1 border-t border-gray-100 dark:border-gray-800" />
          </div>
          <button v-if="canExport" type="button" class="menu-item hidden sm:block" role="menuitem" @click="run(() => emit('exportData'))">↓ 导出数据（Excel）</button>
          <button v-if="hasTrace" type="button" class="menu-item" role="menuitem" @click="run(() => emit('openTrace'))">⚡ 查看执行链路</button>
          <button v-if="hasTokenStats" type="button" class="menu-item" role="menuitem" @click="run(() => emit('openStats'))">▤ 查看调用详情</button>
          <button v-if="canSaveReport" type="button" class="menu-item" role="menuitem" @click="run(() => emit('saveReport'))">☆ 添加固化报表</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.menu-item {
  display: block;
  width: 100%;
  border-radius: 0.5rem;
  padding: 0.5rem 0.625rem;
  text-align: left;
  font-size: 0.75rem;
  color: rgb(75 85 99);
}
.menu-item:hover { background: rgb(249 250 251); }
:global(.dark) .menu-item { color: rgb(209 213 219); }
:global(.dark) .menu-item:hover { background: rgb(31 41 55); }
</style>
