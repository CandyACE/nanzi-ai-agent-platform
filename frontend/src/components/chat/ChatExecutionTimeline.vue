<template>
  <div
    v-if="visible"
    class="mb-1 w-full min-w-0 max-w-[42rem] lg:max-w-[48rem] 2xl:max-w-[52rem]"
  >
    <ChatThinkingHeader
      v-model:expanded="expanded"
      :is-thinking="!hasAnswer && (isThinking || hasPending)"
      :title="headerTitle"
      :step-count="items.length"
      :skill-summary="headerSkillSummary"
      :current-step="currentStep"
      :duration="duration"
      :bordered="bordered"
      :dark-mode="darkMode"
    />

    <transition
      enter-active-class="transition-opacity duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-show="expanded"
        class="mt-0.5 space-y-0.5 px-1 py-0.5"
      >
        <div
          v-if="skillBadges.length"
          class="flex flex-wrap items-center gap-1 rounded-md border border-purple-100/70 bg-purple-50/70 px-1.5 py-1 text-[11px] font-semibold text-purple-700 dark:border-purple-900/30 dark:bg-purple-950/20 dark:text-purple-300"
        >
          <span aria-hidden="true">⚡</span>
          <span>{{ skillNoticeLabel }}</span>
          <span
            v-for="skill in skillBadges"
            :key="skill.key"
            class="rounded-full border border-purple-200/70 bg-purple-100 px-1.5 py-0.5 text-[10px] font-bold dark:border-purple-800/40 dark:bg-purple-900/40"
            :title="skill.description"
          >
            {{ skill.label }}
          </span>
        </div>
        <div
          v-for="item in items"
          :key="item.id"
          class="relative"
        >
          <div v-if="item.kind === 'text'" class="rounded-md px-1 py-0.5 text-[12px] leading-5"
            :class="item.pending ? 'text-gray-600 dark:text-gray-300' : 'text-gray-400 dark:text-gray-500'"
          >
            <div class="flex gap-2">
              <span v-if="item.pending" class="thought-status-dot mt-1 shrink-0" aria-label="进行中" title="进行中" />
              <span v-if="item.textKind !== 'reasoning'" class="mt-0.5 shrink-0" aria-hidden="true">✨</span>
              <span
                v-if="item.sourceLabel && item.textKind !== 'reasoning'"
                class="mt-0.5 shrink-0 text-[10px] font-semibold text-gray-400 dark:text-gray-500"
              >{{ item.sourceLabel }}</span>
              <div class="min-w-0 flex-1">
                <button
                  v-if="item.textKind === 'reasoning'"
                  type="button"
                  class="mb-0.5 flex w-full items-center gap-2 text-left text-[10px] hover:text-gray-600 dark:hover:text-gray-300"
                  :aria-expanded="isReasoningBodyOpen(item)"
                  @click="item.contentExpanded = isReasoningBodyOpen(item) ? false : true"
                >
                  <span aria-hidden="true">💭</span>
                  <span class="min-w-0 flex-1">深度思考</span>
                  <span v-if="formatDuration(item.execution_time_ms)" class="shrink-0 font-mono text-[10px] text-gray-400">{{ formatDuration(item.execution_time_ms) }}</span>
                  <svg class="h-3 w-3 shrink-0 transition-transform" :class="{ 'rotate-180': isReasoningBodyOpen(item) }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m19 9-7 7-7-7" />
                  </svg>
                </button>
                <blockquote
                  v-if="item.textKind === 'reasoning'"
                  v-show="isReasoningBodyOpen(item)"
                  class="mb-0 mt-0.5 border-l-2 border-gray-200 pl-2.5 dark:border-gray-700"
                >
                  <pre class="w-fit max-w-full whitespace-pre-wrap break-words font-sans">{{ item.content }}<span v-if="item.pending" class="ml-0.5 animate-pulse">▌</span></pre>
                </blockquote>
                <pre
                  v-else
                  class="w-fit max-w-full whitespace-pre-wrap break-words font-sans"
                >{{ item.content }}<span v-if="item.pending" class="ml-0.5 animate-pulse">▌</span></pre>
              </div>
            </div>
            <div v-if="item.children?.length" class="ml-5 mt-0.5 border-l border-gray-200/80 pl-1.5 dark:border-gray-700/80">
              <button
                type="button"
                class="mb-0 flex items-center gap-1 text-[10px] text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
                :aria-expanded="item.childrenExpanded !== false"
                @click="item.childrenExpanded = item.childrenExpanded === false"
              >
                <svg class="h-3 w-3 transition-transform" :class="{ 'rotate-180': item.childrenExpanded !== false }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m19 9-7 7-7-7" />
                </svg>
                <span>{{ item.children.length }} 个工具调用</span>
              </button>
              <div v-show="item.childrenExpanded !== false" class="space-y-0">
                <div
                  v-for="child in item.children"
                  :key="child.id"
                  class="rounded-md px-1 py-0.5 text-[11px] leading-5 transition-colors"
                  :class="{
                    'bg-red-50/60 text-red-700 dark:bg-red-950/20 dark:text-red-300': child.status === 'error',
                    'text-gray-600 dark:text-gray-300': child.status === 'pending',
                    'text-gray-400 hover:bg-gray-50 dark:text-gray-500 dark:hover:bg-gray-800/40': child.status !== 'pending' && child.status !== 'error',
                  }"
                >
                  <button
                    type="button"
                    class="flex w-full items-center gap-2 text-left"
                    :aria-expanded="child.children?.length ? child.childrenExpanded !== false : child.isExpanded === true"
                    @click="child.children?.length ? (child.childrenExpanded = child.childrenExpanded === false) : (child.details ? child.isExpanded = !child.isExpanded : undefined)"
                  >
                    <span v-if="child.status === 'pending'" class="thought-status-dot shrink-0" aria-label="进行中" title="进行中" />
                    <span class="inline-flex h-3 w-3 shrink-0 items-center justify-center text-[11px] leading-none" aria-hidden="true">{{ iconFor(child) }}</span>
                    <span class="min-w-0 flex-1 truncate" :title="child.title">
                      <span
                        v-if="child.subagent && !child.children?.length"
                        :title="formatSubagentTraceSummary(child.subagent)"
                      >子代理 · </span>
                      <span>{{ child.title }}</span>
                    </span>
                    <span
                      v-if="child.subagent && subagentStatusLabel(child.status)"
                      class="shrink-0 text-[10px]"
                      :class="child.status === 'error' ? 'text-red-600' : child.status === 'pending' ? 'text-emerald-500 dark:text-emerald-400' : 'text-gray-400'"
                    >
                      {{ subagentStatusLabel(child.status) }}
                    </span>
                    <span v-if="child.status === 'error' && !child.subagent" class="shrink-0 text-[10px]">失败</span>
                    <span v-if="formatDuration(child.execution_time_ms)" class="shrink-0 font-mono text-[10px] text-gray-400">{{ formatDuration(child.execution_time_ms) }}</span>
                    <svg v-if="child.details || child.children?.length" class="h-3 w-3 shrink-0 text-gray-400 transition-transform" :class="{ 'rotate-180': child.children?.length ? (child.childrenExpanded !== false) : child.isExpanded }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m19 9-7 7-7-7" />
                    </svg>
                  </button>
                  <pre v-if="child.details && child.isExpanded && !child.children?.length" class="mt-1 whitespace-pre-wrap break-words border-t border-gray-200/70 pt-1 font-mono text-[10px] leading-relaxed text-gray-500 dark:border-gray-700/70 dark:text-gray-400">{{ child.details }}</pre>

                  <!-- 嵌套展示子代理内部步骤 -->
                  <div v-if="child.children?.length && child.childrenExpanded !== false" class="ml-4 mt-0.5 space-y-0 border-l border-indigo-200/70 pl-2 dark:border-indigo-800/50">
                    <div
                      v-for="subStep in child.children"
                      :key="subStep.id"
                      class="rounded-md px-1 py-0.5 text-[11px] leading-5 transition-colors"
                      :class="{
                        'bg-red-50/60 text-red-700 dark:bg-red-950/20 dark:text-red-300': subStep.status === 'error',
                        'text-gray-600 dark:text-gray-300': subStep.status === 'pending',
                        'text-gray-400 hover:bg-gray-50 dark:text-gray-500 dark:hover:bg-gray-800/40': subStep.status !== 'pending' && subStep.status !== 'error',
                      }"
                    >
                      <button
                        type="button"
                        class="flex w-full items-center gap-2 text-left"
                        :aria-expanded="subStep.isExpanded === true"
                        @click="subStep.details ? subStep.isExpanded = !subStep.isExpanded : undefined"
                      >
                        <span v-if="subStep.status === 'pending'" class="thought-status-dot shrink-0" aria-label="进行中" title="进行中" />
                        <span class="inline-flex h-3 w-3 shrink-0 items-center justify-center text-[11px] leading-none" aria-hidden="true">{{ iconFor(subStep) }}</span>
                        <span class="min-w-0 flex-1 truncate" :title="subStep.title">{{ subStep.title }}</span>
                        <span v-if="subStep.status === 'error'" class="shrink-0 text-[10px] text-red-600">失败</span>
                        <span v-if="formatDuration(subStep.execution_time_ms)" class="shrink-0 font-mono text-[10px] text-gray-400">{{ formatDuration(subStep.execution_time_ms) }}</span>
                        <svg v-if="subStep.details" class="h-3 w-3 shrink-0 text-gray-400 transition-transform" :class="{ 'rotate-180': subStep.isExpanded }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m19 9-7 7-7-7" />
                        </svg>
                      </button>
                      <pre v-if="subStep.details && subStep.isExpanded" class="mt-1 whitespace-pre-wrap break-words border-t border-gray-200/70 pt-1 font-mono text-[10px] leading-relaxed text-gray-500 dark:border-gray-700/70 dark:text-gray-400">{{ subStep.details }}</pre>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div
            v-else
            class="rounded-lg px-1 py-0.5 text-[11px] leading-5 transition-colors"
            :class="{
              'bg-red-50/60 text-red-700 dark:bg-red-950/20 dark:text-red-300': item.status === 'error',
              'text-gray-600 dark:text-gray-300': item.status === 'pending',
              'text-gray-400 hover:bg-gray-50 dark:text-gray-500 dark:hover:bg-gray-800/40': item.status !== 'pending' && item.status !== 'error',
            }"
          >
            <button
              type="button"
              class="flex w-full items-center gap-2 text-left"
              :aria-expanded="item.children?.length ? item.childrenExpanded !== false : item.isExpanded === true"
              @click="item.children?.length ? (item.childrenExpanded = item.childrenExpanded === false) : (item.details ? item.isExpanded = !item.isExpanded : undefined)"
            >
              <span v-if="item.status === 'pending'" class="thought-status-dot shrink-0" aria-label="进行中" title="进行中" />
              <span class="inline-flex h-3 w-3 shrink-0 items-center justify-center text-[11px] leading-none" aria-hidden="true">{{ iconFor(item) }}</span>
              <span class="min-w-0 flex-1 truncate" :title="item.title">
                <span
                  v-if="item.subagent && !item.children?.length"
                  :title="formatSubagentTraceSummary(item.subagent)"
                >子代理 · </span>
                <span>{{ item.title }}</span>
              </span>
              <span
                v-if="item.subagent && subagentStatusLabel(item.status)"
                class="shrink-0 text-[10px]"
                :class="item.status === 'error' ? 'text-red-600' : item.status === 'pending' ? 'text-emerald-500 dark:text-emerald-400' : 'text-gray-400'"
              >
                {{ subagentStatusLabel(item.status) }}
              </span>
              <span v-if="item.status === 'error' && !item.subagent" class="shrink-0 text-[10px]">失败</span>
              <span v-if="formatDuration(item.execution_time_ms)" class="shrink-0 font-mono text-[10px] text-gray-400">
                {{ formatDuration(item.execution_time_ms) }}
              </span>
              <svg
                v-if="item.details || item.children?.length"
                class="h-3 w-3 shrink-0 text-gray-400 transition-transform"
                :class="{ 'rotate-180': item.children?.length ? (item.childrenExpanded !== false) : item.isExpanded }"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m19 9-7 7-7-7" />
              </svg>
            </button>
            <pre v-if="item.details && item.isExpanded && !item.children?.length" class="mt-1 whitespace-pre-wrap break-words border-t border-gray-200/70 pt-1 font-mono text-[10px] leading-relaxed text-gray-500 dark:border-gray-700/70 dark:text-gray-400">{{ item.details }}</pre>

            <!-- 嵌套展示根级别子代理内部步骤 -->
            <div v-if="item.children?.length && item.childrenExpanded !== false" class="ml-4 mt-0.5 space-y-0 border-l border-indigo-200/70 pl-2 dark:border-indigo-800/50">
              <div
                v-for="subStep in item.children"
                :key="subStep.id"
                class="rounded-md px-1 py-0.5 text-[11px] leading-5 transition-colors"
                :class="{
                  'bg-red-50/60 text-red-700 dark:bg-red-950/20 dark:text-red-300': subStep.status === 'error',
                  'text-gray-600 dark:text-gray-300': subStep.status === 'pending',
                  'text-gray-400 hover:bg-gray-50 dark:text-gray-500 dark:hover:bg-gray-800/40': subStep.status !== 'pending' && subStep.status !== 'error',
                }"
              >
                <button
                  type="button"
                  class="flex w-full items-center gap-2 text-left"
                  :aria-expanded="subStep.isExpanded === true"
                  @click="subStep.details ? subStep.isExpanded = !subStep.isExpanded : undefined"
                >
                  <span v-if="subStep.status === 'pending'" class="thought-status-dot shrink-0" aria-label="进行中" title="进行中" />
                  <span class="inline-flex h-3 w-3 shrink-0 items-center justify-center text-[11px] leading-none" aria-hidden="true">{{ iconFor(subStep) }}</span>
                  <span class="min-w-0 flex-1 truncate" :title="subStep.title">{{ subStep.title }}</span>
                  <span v-if="subStep.status === 'error'" class="shrink-0 text-[10px] text-red-600">失败</span>
                  <span v-if="formatDuration(subStep.execution_time_ms)" class="shrink-0 font-mono text-[10px] text-gray-400">{{ formatDuration(subStep.execution_time_ms) }}</span>
                  <svg v-if="subStep.details" class="h-3 w-3 shrink-0 text-gray-400 transition-transform" :class="{ 'rotate-180': subStep.isExpanded }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m19 9-7 7-7-7" />
                  </svg>
                </button>
                <pre v-if="subStep.details && subStep.isExpanded" class="mt-1 whitespace-pre-wrap break-words border-t border-gray-200/70 pt-1 font-mono text-[10px] leading-relaxed text-gray-500 dark:border-gray-700/70 dark:text-gray-400">{{ subStep.details }}</pre>
              </div>
            </div>
          </div>
        </div>

        <div v-if="isThinking && !items.length" class="px-2 py-1 text-xs text-gray-400 animate-pulse">
          {{ thinkingText || '正在处理…' }}
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from "vue";
import ChatThinkingHeader from "@/components/chat/ChatThinkingHeader.vue";
import {
  skillFlowNoticeLabel,
  summarizeSkillFlowBadges,
  type SkillFlowBadge,
} from "@/utils/skillFlowBadges";
import {
  buildLegacyProcessTimeline,
  isReasoningContentExpanded,
  mergeTimelineLogs,
  resolveTimelineCurrentStep,
  timelineHasPending,
  type ProcessTimelineItem,
  type ProcessTimelineLogItem,
  type ProcessTimelineTextItem,
} from "@/utils/processTimeline";
import {
  formatSubagentTraceSummary,
} from "@/utils/subagentTrace";

const props = withDefaults(defineProps<{
  timeline?: ProcessTimelineItem[];
  logs?: Array<{
    id: string | number;
    title: string;
    details: string;
    status: "pending" | "success" | "error" | "warning";
    category?: string;
    execution_time_ms?: number | null;
    started_at?: number | null;
    subagent?: ProcessTimelineLogItem["subagent"];
  }>;
  reasoningContent?: string;
  processNarration?: string;
  processNarrationPending?: string;
  isThinking?: boolean;
  hasAnswer?: boolean;
  thinkingText?: string;
  duration?: string;
  skillSummary?: string;
  skillBadges?: SkillFlowBadge[];
  bordered?: boolean;
  darkMode?: boolean;
}>(), {
  timeline: () => [],
  logs: () => [],
  reasoningContent: "",
  processNarration: "",
  processNarrationPending: "",
  isThinking: false,
  hasAnswer: false,
  thinkingText: "",
  duration: "",
  skillSummary: "",
  skillBadges: () => [],
  bordered: false,
  darkMode: false,
});

const expanded = defineModel<boolean>("expanded", { default: false });

const items = computed(() => props.timeline.length
  ? mergeTimelineLogs(props.timeline, props.logs)
  : buildLegacyProcessTimeline(props));

const hasPending = computed(() => timelineHasPending(items.value));

const headerTitle = computed(() => props.hasAnswer ? "执行完成" : "执行过程");
const currentStep = computed(() => resolveTimelineCurrentStep(
  items.value,
  Boolean(!props.hasAnswer && (props.isThinking || hasPending.value)),
) || (!props.hasAnswer && props.isThinking ? props.thinkingText : ""));

const visible = computed(() => Boolean(props.isThinking || items.value.length || props.skillBadges.length));
const skillNoticeLabel = computed(() => skillFlowNoticeLabel(props.skillBadges));
const headerSkillSummary = computed(() =>
  props.skillSummary || summarizeSkillFlowBadges(props.skillBadges)
);

watch(hasPending, (pending) => {
  if (pending && !props.hasAnswer) expanded.value = true;
}, { immediate: true });

watch(() => props.hasAnswer, (answer) => {
  if (answer) expanded.value = false;
}, { immediate: true });

function isReasoningBodyOpen(item: ProcessTimelineTextItem): boolean {
  return isReasoningContentExpanded(item);
}

function iconFor(item: ProcessTimelineLogItem): string {
  if (item.category === "tool_resolution") return item.status === "error" ? "⚠️" : "🧭";
  if (item.status === "error") return "⚠️";
  if (item.subagent || item.category === "agent") return "🤖";
  if (item.category === "tool" || item.category === "sql" || item.title.includes("工具")) return "🔧";
  if (item.category === "model" || item.title.includes("模型")) return "✦";
  if (
    item.category === "router"
    || item.category === "intent"
    || item.title.includes("路由")
    || item.title.includes("意图")
  ) return "🧠";
  if (item.category === "permission") return "🔒";
  return "•";
}

function subagentStatusLabel(status: ProcessTimelineLogItem["status"]): string {
  if (status === "pending") return "进行中";
  if (status === "error") return "失败";
  return "已完成";
}

function formatDuration(duration?: number | null): string {
  if (duration === undefined || duration === null || Number.isNaN(duration) || duration <= 0) return "";
  return duration < 1000 ? `${Math.max(1, Math.round(duration))}ms` : `${(duration / 1000).toFixed(1)}s`;
}
</script>

<style scoped>
.thought-status-dot {
  display: inline-block;
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 9999px;
  background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.35);
  animation: thought-status-breathe 1.6s ease-in-out infinite;
}

@keyframes thought-status-breathe {
  0%, 100% { opacity: 0.55; transform: scale(0.85); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.28); }
  50% { opacity: 1; transform: scale(1.15); box-shadow: 0 0 0 0.28rem rgba(34, 197, 94, 0.08); }
}

@media (prefers-reduced-motion: reduce) {
  .thought-status-dot {
    animation: none;
  }
}
</style>
