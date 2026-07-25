<template>
  <div
    v-if="visible"
    class="px-6 py-3 rounded-xl border shadow-lg flex items-center space-x-3 transition-all duration-300 ease-out toast-bounce-in"
    :class="[
      inline ? '' : 'fixed top-8 left-1/2 -translate-x-1/2 z-[9999]',
      visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2',
      type === 'success'
        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
        : type === 'warning'
          ? 'bg-amber-50 text-amber-700 border-amber-200'
          : type === 'error'
            ? 'bg-red-50 text-red-700 border-red-200'
            : 'bg-blue-50 text-blue-700 border-blue-200',
    ]"
  >
    <!-- Success -->
    <svg v-if="type === 'success'" class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
    <!-- Error -->
    <svg v-else-if="type === 'error'" class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
    <!-- Warning -->
    <svg v-else-if="type === 'warning'" class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
    <!-- Info -->
    <svg v-else class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>

    <span class="font-bold text-sm">{{ message }}</span>

    <button
      type="button"
      @click="close"
      class="ml-1 -mr-1 inline-flex rounded-md p-0.5 opacity-80 hover:opacity-100 focus:outline-none"
      aria-label="关闭"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

<style scoped>
@keyframes toast-bounce-in {
  0% {
    transform: translateY(-10px);
    opacity: 0;
  }
  60% {
    transform: translateY(4px);
    opacity: 1;
  }
  100% {
    transform: translateY(0);
  }
}
.toast-bounce-in {
  animation: toast-bounce-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
</style>
