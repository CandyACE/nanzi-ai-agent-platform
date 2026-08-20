<template>
  <div
    v-if="visible"
    class="px-4 py-2 rounded-2xl border flex items-center space-x-2.5 transition-all duration-300 ease-out select-none shadow-xl"
    :class="[
      inline ? '' : 'fixed top-6 left-1/2 -translate-x-1/2 z-[100000]',
      visible ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 -translate-y-2 scale-95',
      type === 'success'
        ? 'bg-white dark:bg-zinc-900 bg-gradient-to-r from-emerald-50 via-white to-white dark:from-emerald-950/60 dark:via-zinc-900 dark:to-zinc-900 border-emerald-200 dark:border-emerald-800/80 shadow-emerald-950/10 dark:shadow-black/60'
        : type === 'warning'
          ? 'bg-white dark:bg-zinc-900 bg-gradient-to-r from-amber-50 via-white to-white dark:from-amber-950/60 dark:via-zinc-900 dark:to-zinc-900 border-amber-200 dark:border-amber-800/80 shadow-amber-950/10 dark:shadow-black/60'
          : type === 'error'
            ? 'bg-white dark:bg-zinc-900 bg-gradient-to-r from-rose-50 via-white to-white dark:from-rose-950/60 dark:via-zinc-900 dark:to-zinc-900 border-rose-200 dark:border-rose-800/80 shadow-rose-950/10 dark:shadow-black/60'
            : 'bg-white dark:bg-zinc-900 bg-gradient-to-r from-sky-50 via-white to-white dark:from-sky-950/60 dark:via-zinc-900 dark:to-zinc-900 border-sky-200 dark:border-sky-800/80 shadow-sky-950/10 dark:shadow-black/60',
    ]"
  >
    <!-- Success Icon -->
    <div v-if="type === 'success'" class="w-5 h-5 rounded-full bg-emerald-500 text-white flex items-center justify-center shrink-0 shadow-sm shadow-emerald-500/30">
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    </div>
    <!-- Error Icon -->
    <div v-else-if="type === 'error'" class="w-5 h-5 rounded-full bg-rose-500 text-white flex items-center justify-center shrink-0 shadow-sm shadow-rose-500/30">
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </div>
    <!-- Warning Icon -->
    <div v-else-if="type === 'warning'" class="w-5 h-5 rounded-full bg-amber-500 text-white flex items-center justify-center shrink-0 shadow-sm shadow-amber-500/30">
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01" />
      </svg>
    </div>
    <!-- Info Icon -->
    <div v-else class="w-5 h-5 rounded-full bg-sky-500 text-white flex items-center justify-center shrink-0 shadow-sm shadow-sky-500/30">
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01" />
      </svg>
    </div>

    <!-- Message -->
    <span
      class="font-medium text-xs sm:text-sm tracking-tight"
      :class="[
        type === 'success'
          ? 'text-emerald-950 dark:text-emerald-50'
          : type === 'warning'
            ? 'text-amber-950 dark:text-amber-50'
            : type === 'error'
              ? 'text-rose-950 dark:text-rose-50'
              : 'text-sky-950 dark:text-sky-50',
      ]"
    >
      {{ message }}
    </span>

    <!-- Close Button -->
    <button
      type="button"
      @click="close"
      class="ml-1 -mr-0.5 p-1 rounded-full text-zinc-400 hover:text-zinc-600 dark:text-zinc-500 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors focus:outline-none"
      aria-label="关闭"
    >
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface Props {
  message: string
  type?: 'success' | 'error' | 'warning' | 'info'
  duration?: number
  /** 在 ToastContainer 内堆叠时关闭自身 fixed 定位 */
  inline?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  type: 'info',
  duration: 3000,
  inline: false,
})

const emit = defineEmits<{
  close: []
}>()

const visible = ref(false)

const close = () => {
  visible.value = false
  setTimeout(() => {
    emit('close')
  }, 200)
}

onMounted(() => {
  visible.value = true
  if (props.duration > 0) {
    setTimeout(() => {
      close()
    }, props.duration)
  }
})
</script>
