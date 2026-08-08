<script setup lang="ts">
import { formatTokenCompact } from "@/utils/tokenFormat"
import type { WorkbenchPersonalResource } from "@/types/workbench"

withDefaults(
  defineProps<{
    items: WorkbenchPersonalResource[]
    /** Embed 欢迎页：强制一行 5 卡 + 更紧凑字号 */
    compact?: boolean
  }>(),
  { compact: false },
)

const emit = defineEmits<{
  (e: "select", item: WorkbenchPersonalResource): void
}>()

const displayValue = (item: WorkbenchPersonalResource) => {
  if (item.status === "error") return "--"
  if (item.key === "tokens") return formatTokenCompact(item.value)
  return String(item.value ?? 0)
}
</script>

<template>
  <section
    v-if="items.length"
    class="grid"
    :class="compact
      ? 'grid-cols-2 gap-2 sm:grid-cols-5'
      : 'grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-6'"
  >
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="border bg-white text-left shadow-sm transition hover:border-blue-200 hover:bg-blue-50/40 dark:bg-gray-800/50 dark:hover:border-primary/40 dark:hover:bg-blue-900/10"
      :class="[
        compact
          ? 'rounded-xl px-2.5 py-2 sm:rounded-xl sm:px-2 sm:py-1.5'
          : 'rounded-2xl px-3.5 py-3',
        item.status === 'error' ? 'border-amber-200 dark:border-amber-700/60' : 'border-gray-100 dark:border-gray-700',
      ]"
      @click="emit('select', item)"
    >
      <p
        class="truncate font-medium text-gray-500 dark:text-gray-400"
        :class="compact ? 'text-[11px] sm:text-[9px] sm:leading-tight' : 'text-[11px]'"
      >
        {{ item.label }}
      </p>
      <p
        class="truncate font-bold tracking-tight text-gray-900 tabular-nums dark:text-gray-100"
        :class="compact ? 'mt-1 text-lg sm:mt-0.5 sm:text-sm' : 'mt-1.5 text-xl'"
      >
        {{ displayValue(item) }}
      </p>
      <p
        class="truncate text-gray-400 dark:text-gray-500"
        :class="compact ? 'mt-0.5 text-[10px] sm:text-[9px] sm:leading-tight' : 'mt-0.5 text-[11px]'"
      >
        <span v-if="item.status === 'error'">暂时无法获取</span>
        <span v-else>{{ item.unit }}</span>
      </p>
    </button>
  </section>
</template>
