<template>
  <div
    v-if="visible"
    class="px-4 py-2 rounded-2xl border flex items-center space-x-2.5 transition-all duration-300 ease-out backdrop-blur-md"
    :class="[
      inline ? '' : 'fixed top-6 left-1/2 -translate-x-1/2 z-[9999]',
      visible ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 -translate-y-2 scale-95',
      type === 'success'
        ? 'bg-gradient-to-r from-emerald-50/90 via-white/95 to-emerald-50/60 dark:from-emerald-950/40 dark:via-zinc-900/95 dark:to-emerald-950/30 border-emerald-200/80 dark:border-emerald-800/60 shadow-lg shadow-emerald-500/10 dark:shadow-emerald-950/40'
        : type === 'warning'
          ? 'bg-gradient-to-r from-amber-50/90 via-white/95 to-amber-50/60 dark:from-amber-950/40 dark:via-zinc-900/95 dark:to-amber-950/30 border-amber-200/80 dark:border-amber-800/60 shadow-lg shadow-amber-500/10 dark:shadow-amber-950/40'
          : type === 'error'
            ? 'bg-gradient-to-r from-rose-50/90 via-white/95 to-rose-50/60 dark:from-rose-950/40 dark:via-zinc-900/95 dark:to-rose-950/30 border-rose-200/80 dark:border-rose-800/60 shadow-lg shadow-rose-500/10 dark:shadow-rose-950/40'
            : 'bg-gradient-to-r from-sky-50/90 via-white/95 to-sky-50/60 dark:from-sky-950/40 dark:via-zinc-900/95 dark:to-sky-950/30 border-sky-200/80 dark:border-sky-800/60 shadow-lg shadow-sky-500/10 dark:shadow-sky-950/40',
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
      class="font-medium text-xs sm:text-sm select-none tracking-tight"
      :class="[
        type === 'success'
          ? 'text-emerald-950 dark:text-emerald-100'
          : type === 'warning'
            ? 'text-amber-950 dark:text-amber-100'
            : type === 'error'
              ? 'text-rose-950 dark:text-rose-100'
              : 'text-sky-950 dark:text-sky-100',
      ]"
    >
      {{ message }}
    </span>

    <!-- Close Button -->
    <button
      type="button"
      @click="close"
      class="ml-1 -mr-0.5 p-1 rounded-full text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 transition-colors focus:outline-none"
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
