<template>
  <div class="space-y-3">
    <!-- ① 数据 / 文件 -->
    <section
      v-if="hasConversationDataFile"
      data-section="data"
      class="space-y-0.5"
      :class="props.focus === 'data' ? 'rounded-xl border-l-2 border-primary bg-primary/5 py-1.5 pl-2 pr-1' : ''"
    >
      <div class="flex items-center gap-1.5 px-0.5 pb-1">
        <span class="text-[10px] font-semibold tracking-wide text-gray-400 dark:text-gray-500">数据 / 文件</span>
        <span v-if="reusableCount > 0" class="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white">数据 {{ reusableCount }}</span>
        <span v-if="artifactCount > 0" class="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white">文件 {{ artifactCount }}</span>
      </div>
      <button
        v-if="hasReusableResultEntry"
        type="button"
        class="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs text-gray-600 transition-colors hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
        @click="run(() => emit('openReusableResults'))"
      >
        <span>▤ 查看可复用结果</span>
        <span v-if="conversationReusableCount > 0" class="text-[10px] text-gray-400">{{ conversationReusableCount }} 条</span>
      </button>
      <button
        v-if="canExport"
        type="button"
        class="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs text-gray-600 transition-colors hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
        @click="run(() => emit('exportData'))"
      >
        <span>↓ 导出数据（Excel）</span>
      </button>
      <button
        v-if="hasArtifactEntry"
        type="button"
        class="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs text-gray-600 transition-colors hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
        @click="run(() => emit('openArtifacts'))"
      >
        <span>▣ 查看文件产物</span>
        <span v-if="conversationArtifactCount > 0" class="text-[10px] text-gray-400">{{ conversationArtifactCount }} 个</span>
      </button>
    </section>

    <!-- ② 继续分析（通用四件套 / ChatBI 推荐追问） -->
    <section v-if="continueActions.length" data-section="continue" class="space-y-0.5">
      <div class="px-0.5 pb-1 text-[10px] font-semibold tracking-wide text-gray-400 dark:text-gray-500">继续分析</div>
      <button
        v-for="action in continueActions"
        :key="action.id"
        type="button"
        class="flex w-full items-start gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
        @click="run(() => selectContinue(action))"
      >
        <span class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-gray-100 text-[11px] text-gray-500 dark:bg-gray-800 dark:text-gray-400">{{ iconFor(action.id) }}</span>
        <span class="min-w-0">
          <span class="block text-xs font-semibold text-gray-700 dark:text-gray-200">{{ action.label }}</span>
          <span v-if="action.description" class="mt-0.5 block text-[10px] leading-relaxed text-gray-400">{{ action.description }}</span>
        </span>
      </button>
    </section>

    <!-- ③ 本次调用 -->
    <section v-if="hasTokenStats || hasTrace" data-section="call" class="space-y-0.5">
      <div class="px-0.5 pb-1 text-[10px] font-semibold tracking-wide text-gray-400 dark:text-gray-500">本次调用</div>
      <button
        v-if="hasTokenStats"
        type="button"
        class="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs text-gray-600 transition-colors hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
        @click="run(() => emit('openStats'))"
      >
        <span>▤ 查看调用详情</span>
        <span class="text-[10px] text-gray-400">{{ tokenLabel }}</span>
      </button>
      <button
        v-if="hasTrace"
        type="button"
        class="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs text-gray-600 transition-colors hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
        @click="run(() => emit('openTrace'))"
      >
        <span>↗ 查看执行链路</span>
      </button>
    </section>

    <!-- ④ 沉淀 -->
    <section v-if="canSaveReport" data-section="report" class="space-y-0.5">
      <div class="px-0.5 pb-1 text-[10px] font-semibold tracking-wide text-gray-400 dark:text-gray-500">沉淀</div>
      <button
        type="button"
        class="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs text-gray-600 transition-colors hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
        @click="run(() => emit('saveReport'))"
      >
        <span>☆ 添加固化报表</span>
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type { ChatBIInsightAction } from "@/types/chatbiInsight";
import {
  CONTINUE_ANALYSIS_ACTIONS,
  chatbiActionIcon,
  continueActionIcon,
  type ContinueAction,
} from "./continueAnalysisActions";

/**
 * 移动端操作抽屉的内容：四组（数据 / 文件、继续分析、本次调用、沉淀）。
 *
 * 空组不渲染；focus === 'data' 时数据组高亮（点操作栏「▤ 数据」进来时）。
 * ChatBI 追问与通用沉淀动作共用同一套渲染，但事件分开上抛：ChatBI 的
 * local_action 需要原始 action 对象才能分派。
 */
const props = defineProps<{
  focus: "data" | null;
  hasConversationDataFile: boolean;
  reusableCount: number;
  artifactCount: number;
  hasReusableResultEntry: boolean;
  hasArtifactEntry: boolean;
  conversationReusableCount: number;
  conversationArtifactCount: number;
  canExport: boolean;
  hasTrace: boolean;
  hasTokenStats: boolean;
  tokenLabel: string;
  canSaveReport: boolean;
  chatbiActions: ChatBIInsightAction[];
  showGenericContinue: boolean;
}>();

const emit = defineEmits<{
  (event: "exportData"): void;
  (event: "openReusableResults"): void;
  (event: "openArtifacts"): void;
  (event: "openTrace"): void;
  (event: "openStats"): void;
  (event: "saveReport"): void;
  (event: "continueAnalysis", query: string): void;
  (event: "chatbiAction", action: ChatBIInsightAction): void;
  (event: "close"): void;
}>();

/** 与桌面 MessageActionMenus 的 run 语义一致：先收起抽屉，再执行动作，避免抽屉压在后续面板上。 */
const run = (action: () => void) => {
  emit("close");
  action();
};

const isChatbi = computed(() => props.chatbiActions.length > 0);
const continueActions = computed<(ContinueAction | ChatBIInsightAction)[]>(() => {
  if (isChatbi.value) return props.chatbiActions.slice(0, 6);
  return props.showGenericContinue ? CONTINUE_ANALYSIS_ACTIONS : [];
});
const iconFor = (id: string) => (isChatbi.value ? chatbiActionIcon(id) : continueActionIcon(id));
const selectContinue = (action: ContinueAction | ChatBIInsightAction) => {
  if (isChatbi.value) {
    emit("chatbiAction", action as ChatBIInsightAction);
    return;
  }
  emit("continueAnalysis", (action as ContinueAction).query);
};
</script>
