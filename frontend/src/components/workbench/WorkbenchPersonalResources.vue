<script setup lang="ts">
import { useRouter } from "vue-router"
import { formatTokenCompact } from "@/utils/tokenFormat"
import type { WorkbenchPersonalResource } from "@/types/workbench"

defineProps<{
  items: WorkbenchPersonalResource[]
}>()

const router = useRouter()

const openResource = (item: WorkbenchPersonalResource) => {
  router.push({ path: "/dashboard/personal", query: { tab: item.tab } })
}

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
      class="rounded-2xl border bg-white px-3.5 py-3 text-left shadow-sm transition hover:border-blue-200 hover:bg-blue-50/40"
      :class="item.status === 'error' ? 'border-amber-200' : 'border-gray-100'"
      @click="openResource(item)"
    >
      <p class="truncate text-[11px] font-medium text-gray-500">{{ item.label }}</p>
      <p class="mt-1.5 truncate text-xl font-bold tracking-tight text-gray-900 tabular-nums">
        {{ displayValue(item) }}
      </p>
      <p class="mt-0.5 truncate text-[11px] text-gray-400">
        <span v-if="item.status === 'error'">暂时无法获取</span>
        <span v-else>{{ item.unit }}</span>
      </p>
    </button>
  </section>
</template>
