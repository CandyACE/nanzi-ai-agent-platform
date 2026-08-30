<script setup lang="ts">
withDefaults(defineProps<{
  status?: 'saved' | 'reused' | 'fallback' | string | null
  resultId?: string | null
  originName?: string | null
  count?: number | null
}>(), {
  status: null,
  resultId: null,
  originName: null,
  count: null,
})

const emit = defineEmits<{
  open: []
}>()
</script>

<template>
  <button
    v-if="status === 'saved' || status === 'reused'"
    type="button"
    class="inline-flex max-w-full items-center gap-1 rounded-md px-1.5 py-1 text-[10px] text-gray-400 transition-colors hover:bg-primary/10 hover:text-primary dark:text-gray-500"
    :title="status === 'saved' ? '本轮生成的数据可用于后续分析' : status === 'reused' ? '本次回答引用了上一轮已生成的数据' : '本次未使用已有可复用数据'"
    @click="emit('open')"
  >
    <span class="shrink-0" aria-hidden="true">{{ status === 'saved' ? '▣' : status === 'reused' ? '↻' : '↗' }}</span>
    <span class="truncate">
      <template v-if="status === 'saved'">可复用数据</template>
      <template v-else-if="status === 'reused'">引用上一轮数据</template>
      <template v-else>未使用已有数据</template>
    </span>
    <span v-if="count && count > 0" class="shrink-0">({{ count }})</span>
  </button>
</template>
