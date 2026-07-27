<script setup lang="ts">
import { ref } from 'vue'
import McpServerRegistry from '../components/system/McpServerRegistry.vue'

const activeScope = ref<'global' | 'personal'>('global')
</script>

<template>
  <div class="h-full flex flex-col space-y-4 overflow-hidden">
    <!-- Header 标题栏：参考 Skills 工作台标题样式 -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 flex-shrink-0">
      <div class="flex items-center space-x-3">
        <h1 class="text-xl sm:text-2xl font-bold tracking-tight text-gray-900 dark:text-white">MCP 工具集</h1>
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
          Model Context Protocol
        </span>
      </div>
      <p class="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
        接入并管理外部 MCP SSE 服务端，自动识别工具集并无缝绑定至智能体生态
      </p>
    </div>

    <!-- Scope Tab 切换：参考 Skills 工作台的设计（平台 MCP / 我的 MCP） -->
    <div class="flex items-center border-b border-gray-200 dark:border-gray-800 flex-shrink-0">
      <button
        id="tab-global-mcp"
        type="button"
        @click="activeScope = 'global'"
        class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer"
        :class="activeScope === 'global' ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400 font-bold' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
        </svg>
        平台 MCP
      </button>
      <button
        id="tab-personal-mcp"
        type="button"
        @click="activeScope = 'personal'"
        class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer"
        :class="activeScope === 'personal' ? 'border-emerald-600 text-emerald-600 dark:border-emerald-400 dark:text-emerald-400 font-bold' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        我的 MCP
      </button>
    </div>

    <!-- 主体区域：传入 activeScope -->
    <div class="flex-1 min-h-0 overflow-hidden">
      <McpServerRegistry :key="activeScope" :scope="activeScope" />
    </div>
  </div>
</template>
