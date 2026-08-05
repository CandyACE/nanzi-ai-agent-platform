<script setup lang="ts">
import ToastContainer from './components/ToastContainer.vue'
import { onMounted } from 'vue'
import { loadBranding } from './composables/useBranding'
import { initializeTheme } from './composables/useAppTheme'

onMounted(() => {
  loadBranding()
  initializeTheme()
})
</script>

<template>
  <ToastContainer />
  <router-view></router-view>
</template>

<style>
</style>
