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
    v-if="status"
    type="button"
    class="inline-flex max-w-full items-center gap-1 rounded-md px-1.5 py-1 text-[10px] text-gray-400 transition-colors hover:bg-primary/10 hover:text-primary dark:text-gray-500"
    :title="status === 'saved' ? '本轮结果已保存，可在 AI 产物中复用' : status === 'reused' ? '本轮优先复用了已保存结果' : '未找到可复用结果，已回退到原查询流程'"
    @click="emit('open')"
  >
    <span class="shrink-0" aria-hidden="true">{{ status === 'saved' ? '▣' : status === 'reused' ? '↻' : '↗' }}</span>
    <span class="truncate">
      <template v-if="status === 'saved'">已保存</template>
      <template v-else-if="status === 'reused'">已复用</template>
      <template v-else>已回退</template>
    </span>
    <span v-if="count && count > 0" class="shrink-0">· {{ count }}</span>
  </button>
</template>
