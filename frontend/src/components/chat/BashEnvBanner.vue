<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  env: 'docker' | 'host'
}>()

const emit = defineEmits<{
  (e: 'dismiss'): void
  (e: 'ignore'): void
}>()

const isDocker = computed(() => props.env === 'docker')
const isHost = computed(() => props.env === 'host')
</script>

<template>
  <div
    role="status"
    :class="
      isDocker
        ? 'mb-2 flex flex-wrap items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50/90 px-3 py-2 text-xs text-emerald-900 shadow-sm dark:border-emerald-500/30 dark:bg-emerald-950/40 dark:text-emerald-100'
        : 'mb-2 flex flex-wrap items-center gap-2 rounded-xl border border-amber-200 bg-amber-50/90 px-3 py-2 text-xs text-amber-900 shadow-sm dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-100'
    "
  >
    <template v-if="isDocker">
      <span class="font-semibold">🟢 Bash 运行在容器环境</span>
      <span class="text-emerald-700/80 dark:text-emerald-200/70">
        仍需遵守命令安全规则，容器环境不等于绝对安全
      </span>
    </template>
    <template v-else>
      <span class="font-semibold">⚠️ Bash 运行在宿主机上</span>
      <span class="text-amber-700/80 dark:text-amber-200/70">
        Bash 直接在后端进程所在环境执行，存在命令风险，建议 Docker 部署或改用 sandbox
      </span>
    </template>
    <div class="ml-auto flex items-center gap-2">
      <button
        type="button"
        :class="
          isDocker
            ? 'rounded-lg px-2 py-1 text-emerald-700/60 hover:bg-emerald-100/80 dark:text-emerald-200/60 dark:hover:bg-emerald-900/60'
            : 'rounded-lg px-2 py-1 text-amber-700/60 hover:bg-amber-100/80 dark:text-amber-200/60 dark:hover:bg-amber-900/60'
        "
        aria-label="忽略提示"
        @click="emit('ignore')"
      >
        忽略提示
      </button>
      <button
        type="button"
        :class="
          isDocker
            ? 'rounded-lg px-2 py-1 text-emerald-700/70 hover:bg-emerald-100/80 dark:text-emerald-200/70 dark:hover:bg-emerald-900/60'
            : 'rounded-lg px-2 py-1 text-amber-700/70 hover:bg-amber-100/80 dark:text-amber-200/70 dark:hover:bg-amber-900/60'
        "
        aria-label="关闭"
        @click="emit('dismiss')"
      >
        ✕
      </button>
    </div>
  </div>
</template>
