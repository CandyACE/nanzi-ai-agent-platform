<template>
  <div class="fixed top-8 left-1/2 -translate-x-1/2 z-[100000] flex flex-col items-center gap-2 pointer-events-none">
    <TransitionGroup
      enter-active-class="transition ease-out duration-300"
      enter-from-class="transform -translate-y-3 opacity-0"
      enter-to-class="transform translate-y-0 opacity-100"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="transform translate-y-0 opacity-100"
      leave-to-class="transform -translate-y-2 opacity-0"
    >
      <Toast
        v-for="toast in toasts"
        :key="toast.id"
        :message="toast.message"
        :type="toast.type"
        :duration="toast.duration"
        inline
        @close="removeToast(toast.id)"
        class="pointer-events-auto"
      />
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { useToast } from '../composables/useToast'
import Toast from './Toast.vue'

const { toasts, removeToast } = useToast()
</script>
