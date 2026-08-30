<script setup lang="ts">
withDefaults(defineProps<{
  originName?: string | null
}>(), {
  originName: null,
})
</script>

<template>
  <div
    role="note"
    class="mb-2 inline-flex max-w-full items-start gap-2 rounded-lg border border-violet-100 bg-violet-50/80 px-2.5 py-1.5 text-[11px] font-medium leading-relaxed text-violet-700 dark:border-violet-900/50 dark:bg-violet-950/25 dark:text-violet-300"
  >
    <svg class="mt-0.5 h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M12 3a9 9 0 100 18 9 9 0 000-18z" />
    </svg>
    <span>
      <span class="font-semibold">引用提示</span>
      <span class="mx-1 opacity-60">·</span>
      本次回答基于{{ originName ? `上一轮「${originName}」` : '本会话上一轮' }}的可复用结果
    </span>
  </div>
</template>
