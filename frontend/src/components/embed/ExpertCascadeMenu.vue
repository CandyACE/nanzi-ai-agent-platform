<script setup lang="ts">
withDefaults(
  defineProps<{
    routingMode?: string
    expertAgentId?: string
    allowedAgents?: any[]
    isLoadingAgents?: boolean
    compact?: boolean
    /** 移动端底部抽屉内铺满宽度 */
    fullWidth?: boolean
    /** 桌面侧栏浮层：高度铺满左侧加号菜单，上下对齐 */
    fillHeight?: boolean
  }>(),
  {
    routingMode: 'auto',
    expertAgentId: '',
    allowedAgents: () => [],
    isLoadingAgents: false,
    compact: false,
    fullWidth: false,
    fillHeight: false,
  },
)

const emit = defineEmits<{
  (e: 'select-auto'): void
  (e: 'select-expert', agentId: string): void
  (e: 'refresh'): void
  (e: 'close'): void
}>()

const isExpertMode = (routingMode?: string, expertAgentId?: string) =>
  routingMode === 'expert' && !!expertAgentId
</script>

<template>
  <div
    class="flex flex-col overflow-hidden bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-2xl"
    :class="fullWidth
      ? 'w-full max-h-[min(65vh,28rem)] rounded-none border-x-0 border-b-0 shadow-none'
      : fillHeight
        ? 'h-full w-[min(28rem,calc(100vw-1.5rem))] max-h-none rounded-xl shadow-xl'
        : compact
          ? 'w-[min(26rem,calc(100vw-1.25rem))] max-h-[min(58vh,28rem)] rounded-xl shadow-xl'
          : 'w-[min(28rem,calc(100vw-1.5rem))] max-h-[min(60vh,30rem)] rounded-xl shadow-xl'"
    role="menu"
    aria-label="专家中心"
  >
    <div class="px-3 py-2.5 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between shrink-0 bg-white dark:bg-gray-800">
      <div class="flex items-center gap-1.5 min-w-0">
        <span class="w-1 h-3.5 bg-primary rounded-full shrink-0" />
        <span class="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
          专家中心({{ allowedAgents.length }})
        </span>
        <button
          type="button"
          class="text-gray-500 hover:text-primary transition-all p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 shrink-0"
          :class="{ 'animate-spin text-primary': isLoadingAgents }"
          title="刷新列表"
          @click.stop="emit('refresh')"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
      <button
        v-if="!fullWidth"
        type="button"
        class="flex h-7 w-7 items-center justify-center rounded-md text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-700 dark:hover:text-gray-200 shrink-0"
        aria-label="关闭专家中心"
        title="关闭"
        @click.stop="emit('close')"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.25" d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </div>

    <!-- fillHeight 时由父级定高，列表 flex-1 滚动；否则用固定 max-h -->
    <div
      class="overflow-y-auto custom-scrollbar p-2 space-y-0.5 bg-white dark:bg-gray-800"
      :class="fillHeight ? 'flex-1 min-h-0' : 'min-h-[10rem] max-h-[min(48vh,22rem)]'"
    >
      <div v-if="isLoadingAgents && allowedAgents.length === 0" class="flex flex-col items-center justify-center py-12 opacity-50">
        <svg class="w-7 h-7 animate-spin text-primary mb-2" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <span class="text-xs font-medium text-gray-400">同步中</span>
      </div>

      <button
        type="button"
        class="w-full flex items-start gap-2.5 px-2.5 py-2.5 rounded-lg cursor-pointer transition-colors border border-transparent text-left"
        :class="!isExpertMode(routingMode, expertAgentId)
          ? 'bg-primary/10 border-primary/15'
          : 'hover:bg-gray-50 dark:hover:bg-gray-700/60'"
        @click.stop="emit('select-auto')"
      >
        <div class="w-9 h-9 mt-0.5 rounded-full bg-primary/10 flex items-center justify-center text-primary border border-primary/15 shrink-0">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-2">
            <span
              class="text-sm font-semibold truncate"
              :class="!isExpertMode(routingMode, expertAgentId) ? 'text-primary' : 'text-gray-900 dark:text-gray-100'"
            >全能助手 (自动)</span>
            <svg
              v-if="!isExpertMode(routingMode, expertAgentId)"
              class="w-3.5 h-3.5 text-primary shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          </div>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 leading-snug line-clamp-2">智能调度最合适的专家处理</p>
        </div>
      </button>

      <div class="h-px bg-gray-200 dark:bg-gray-700 my-1 mx-1.5" />

      <button
        v-for="agent in allowedAgents"
        :key="agent.id"
        type="button"
        class="w-full flex items-start gap-2.5 px-2.5 py-2.5 rounded-lg cursor-pointer transition-colors border border-transparent text-left"
        :class="isExpertMode(routingMode, expertAgentId) && expertAgentId === agent.id
          ? 'bg-primary/10 border-primary/15'
          : 'hover:bg-gray-50 dark:hover:bg-gray-700/60'"
        :title="agent.description || agent.display_name"
        @click.stop="emit('select-expert', agent.id)"
      >
        <div class="w-9 h-9 mt-0.5 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center overflow-hidden border border-gray-200 dark:border-gray-600 shrink-0">
          <img v-if="agent.avatar_url" :src="agent.avatar_url" class="w-full h-full object-cover" />
          <span v-else class="text-xs font-bold text-gray-500 dark:text-gray-300">{{ Array.from(agent.display_name || 'E')[0] }}</span>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-1 min-w-0">
              <span
                class="text-sm font-semibold truncate"
                :class="isExpertMode(routingMode, expertAgentId) && expertAgentId === agent.id
                  ? 'text-primary'
                  : 'text-gray-900 dark:text-gray-100'"
              >{{ agent.display_name }}</span>
              <span
                v-if="agent.is_system"
                class="shrink-0 px-1 py-px text-[8px] font-semibold rounded bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 uppercase"
              >SYS</span>
            </div>
            <svg
              v-if="isExpertMode(routingMode, expertAgentId) && expertAgentId === agent.id"
              class="w-3.5 h-3.5 text-primary shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          </div>
          <p
            class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 leading-snug line-clamp-2"
            :title="agent.description || '专属能力专家'"
          >{{ agent.description || '专属能力专家' }}</p>
        </div>
      </button>
    </div>

    <div class="px-3 py-2 border-t border-gray-200 dark:border-gray-700 text-center shrink-0 bg-gray-50 dark:bg-gray-900/80">
      <span class="text-[11px] text-gray-500 dark:text-gray-400">共 {{ allowedAgents.length }} 个专家</span>
    </div>
  </div>
</template>
