<script setup lang="ts">
import { ref } from 'vue'
import McpServerRegistry from '../components/system/McpServerRegistry.vue'

const props = withDefaults(defineProps<{
  /** 仅展示「我的 MCP」，用于个人中心（无需 menu:mcp_management） */
  personalOnly?: boolean
}>(), {
  personalOnly: false,
})

const activeScope = ref<'global' | 'personal'>(props.personalOnly ? 'personal' : 'global')
</script>

<template>
  <div
    class="flex flex-col space-y-4"
    :class="personalOnly ? 'min-h-0' : 'h-full overflow-hidden'"
  >
    <!-- Header 标题栏：参考 Skills 工作台标题样式 -->
    <div class="flex flex-shrink-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div class="flex min-w-0 flex-wrap items-center gap-2 sm:gap-3">
        <h1
          class="font-bold tracking-tight text-gray-900 dark:text-white"
          :class="personalOnly ? 'text-lg sm:text-xl' : 'text-xl sm:text-2xl'"
        >
          {{ personalOnly ? '我的 MCP' : 'MCP 工具集' }}
        </h1>
        <span
          v-if="!personalOnly"
          class="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300"
        >
          Model Context Protocol
        </span>
        <span
          v-else
          class="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
        >
          个人私有
        </span>
      </div>
      <p class="text-xs leading-relaxed text-gray-500 dark:text-gray-400 sm:max-w-md sm:text-right sm:text-sm">
        {{
          personalOnly
            ? '登记并管理仅对自己可见的 MCP，可在对话中挂载使用'
            : '接入并管理外部 MCP SSE 服务端，自动识别工具集并无缝绑定至智能体生态'
        }}
      </p>
    </div>

    <!-- Scope Tab：个人中心模式下隐藏平台/个人切换 -->
    <div v-if="!personalOnly" class="flex flex-shrink-0 items-center border-b border-gray-200 dark:border-gray-800">
      <button
        id="tab-global-mcp"
        type="button"
        @click="activeScope = 'global'"
        class="flex cursor-pointer items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors"
        :class="activeScope === 'global' ? 'border-blue-600 font-bold text-blue-600 dark:border-blue-400 dark:text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
        </svg>
        平台 MCP
      </button>
      <button
        id="tab-personal-mcp"
        type="button"
        @click="activeScope = 'personal'"
        class="flex cursor-pointer items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors"
        :class="activeScope === 'personal' ? 'border-emerald-600 font-bold text-emerald-600 dark:border-emerald-400 dark:text-emerald-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        我的 MCP
      </button>
    </div>

    <!-- 主体区域：个人中心随页面滚动；控制台保留定高裁剪 -->
    <div :class="personalOnly ? 'min-h-[28rem]' : 'min-h-0 flex-1 overflow-hidden'">
      <McpServerRegistry :key="activeScope" :scope="activeScope" />
    </div>
  </div>
</template>
