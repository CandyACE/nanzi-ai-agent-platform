<script setup lang="ts">
import { formatTokenCompact } from "@/utils/tokenFormat"
import type { WorkbenchPersonalResource } from "@/types/workbench"

defineProps<{ items: WorkbenchPersonalResource[] }>()

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
  <section v-if="items.length" class="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-6">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="rounded-2xl border bg-white px-3.5 py-3 text-left shadow-sm transition hover:border-blue-200 hover:bg-blue-50/40 dark:bg-gray-800/50 dark:border-gray-700 dark:hover:border-primary/40 dark:hover:bg-blue-900/10"
      :class="item.status === 'error' ? 'border-amber-200 dark:border-amber-700/60' : 'border-gray-100 dark:border-gray-700'"
      @click="emit('select', item)"
    >
      <p class="truncate text-[11px] font-medium text-gray-500 dark:text-gray-400">{{ item.label }}</p>
      <p class="mt-1.5 truncate text-xl font-bold tracking-tight text-gray-900 tabular-nums dark:text-gray-100">
        {{ displayValue(item) }}
      </p>
      <p class="mt-0.5 truncate text-[11px] text-gray-400 dark:text-gray-500">
        <span v-if="item.status === 'error'">暂时无法获取</span>
        <span v-else>{{ item.unit }}</span>
      </p>
    </button>
  </section>
</template>
