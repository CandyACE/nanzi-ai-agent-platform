<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  getToolPermissionDisplay,
  type ToolPermissionDisplay,
} from "@/utils/toolPermissionDisplay";
import type { PendingToolPermission } from "@/utils/agentscopeSseHandlers";
import { copyToClipboard } from "@/utils/clipboard";

const props = defineProps<{
  payload: PendingToolPermission;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (event: "submit", confirmed: boolean): void;
}>();

const expanded = ref(props.payload.status === "pending");
const detailsExpanded = ref(props.payload.status === "pending");
const copied = ref(false);
const copyFailed = ref(false);

const display = computed<ToolPermissionDisplay>(() =>
  getToolPermissionDisplay({
    toolName: props.payload.tool_call?.name,
    args: props.payload.tool_call?.args,
    details: props.payload.details,
  }),
);

const isCompact = computed(() => display.value.isCompact);

const cardTitle = computed(() => {
  const rawTitle = String(props.payload.title || "").trim();
  if (!rawTitle || /^(工具调用确认|工具调用需要确认|需要确认工具调用\s*[:：])/u.test(rawTitle)) {
    return display.value.displayTitle;
  }
  return rawTitle;
});

const detailsId = computed(() => {
  const rawId = props.payload.permission_request_id || "pending";
  return `tool-permission-details-${rawId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
});

const isPending = computed(() => props.payload.status === "pending");
const isSubmitting = computed(() => Boolean(props.payload.isSubmitting));
const locked = computed(() => Boolean(props.disabled) || !isPending.value || isSubmitting.value);

const statusLabel = computed(() => {
  if (isSubmitting.value) return "提交中";
  const labels: Record<PendingToolPermission["status"], string> = {
    pending: "待确认",
    approved: "已允许",
    rejected: "已拒绝",
    expired: "已过期",
    error: "执行异常",
  };
  return labels[props.payload.status] || props.payload.status;
});

const statusMessage = computed(() => {
  if (isSubmitting.value) return "正在提交确认，请稍候…";
  if (props.payload.status === "approved") return "已允许本次执行，任务正在继续。";
  if (props.payload.status === "rejected") return "已拒绝本次执行，任务已暂停。";
  if (props.payload.status === "expired") return "这次确认已过期，请重新发起任务。";
  if (props.payload.status === "error") return "确认或执行过程中出现异常，请稍后重试。";
  return "任务当前暂停，等待你的确认。";
});

const hasDetails = computed(() => Boolean(display.value.commandText || display.value.parameterText));
const detailLabel = computed(() => (display.value.commandText ? "命令详情" : "调用参数"));
const detailSummary = computed(() => {
  if (display.value.commandCount > 1) return `共 ${display.value.commandCount} 项检查`;
  return "查看完整参数";
});

const copyText = computed(() => display.value.commandText || display.value.parameterText);

function toggleCard() {
  expanded.value = !expanded.value;
}

function toggleDetails() {
  detailsExpanded.value = !detailsExpanded.value;
}

async function copyDetails() {
  if (!copyText.value) return;
  let success = false;
  try {
    success = await copyToClipboard(copyText.value);
  } catch {
    success = false;
  }
  copied.value = success;
  copyFailed.value = !success;
  window.setTimeout(() => {
    copied.value = false;
    copyFailed.value = false;
  }, 1800);
}

function submit(confirmed: boolean) {
  if (locked.value) return;
  emit("submit", confirmed);
}

watch(
  () => props.payload.permission_request_id,
  () => {
    expanded.value = props.payload.status === "pending";
    detailsExpanded.value = props.payload.status === "pending";
  },
);

watch(
  () => props.payload.status,
  (nextStatus, previousStatus) => {
    if (nextStatus !== "pending" && previousStatus === "pending") {
      expanded.value = false;
      detailsExpanded.value = false;
    } else if (nextStatus === "pending" && previousStatus !== "pending") {
      expanded.value = true;
      detailsExpanded.value = true;
    }
  },
);
</script>

<template>
  <section
    class="mt-3 w-full min-w-0 max-w-[42rem] rounded-xl border p-3 text-xs shadow-sm transition-all lg:max-w-[48rem] 2xl:max-w-[52rem] sm:p-4"
    :class="display.riskTone === 'low'
      ? 'border-sky-200 bg-sky-50/90 text-sky-950 dark:border-sky-900/50 dark:bg-sky-900/20 dark:text-sky-100'
      : 'border-amber-200 bg-amber-50/90 text-amber-950 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-100'"
    role="region"
    :aria-label="`${cardTitle}，${statusLabel}`"
    :aria-busy="isSubmitting"
  >
    <div class="flex items-start gap-3">
      <div
        class="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg"
        :class="display.riskTone === 'low'
          ? 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300'
          : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'"
        aria-hidden="true"
      >
        <svg v-if="display.riskTone === 'low'" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12.75 11.25 15 15 9.75m6 2.25a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
        <svg v-else class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
        </svg>
      </div>

      <div class="min-w-0 flex-1">
        <div
          class="flex cursor-pointer select-none items-start justify-between gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
          :class="display.riskTone === 'low' ? 'focus-visible:ring-sky-500' : 'focus-visible:ring-amber-500'"
          role="button"
          tabindex="0"
          :aria-expanded="expanded"
          :aria-controls="detailsId"
          :title="expanded ? '点击收起确认详情' : '点击展开确认详情'"
          @click="toggleCard"
          @keydown.enter.prevent="toggleCard"
          @keydown.space.prevent="toggleCard"
        >
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-[10px] font-semibold uppercase tracking-wide opacity-60">{{ isPending ? "需要确认执行" : "工具执行结果" }}</span>
              <h3 class="truncate text-sm font-bold leading-5">{{ cardTitle }}</h3>
              <span
                class="shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold"
                :class="display.riskTone === 'low'
                  ? 'border-sky-200 bg-sky-100 text-sky-700 dark:border-sky-800 dark:bg-sky-900/40 dark:text-sky-300'
                  : 'border-amber-200 bg-amber-100 text-amber-700 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-300'"
              >
                {{ display.toolLabel }}
              </span>
            </div>
            <p v-if="!isCompact" class="mt-1 truncate text-[11px] font-normal opacity-75">{{ display.summary }}</p>
          </div>

          <div class="flex shrink-0 items-center gap-2">
            <span
              class="rounded-full px-2 py-0.5 text-[10px] font-bold"
              aria-live="polite"
              :class="{
                'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300': display.riskTone === 'low' && isPending,
                'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300': display.riskTone === 'standard' && isPending,
                'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300': props.payload.status === 'approved',
                'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300': props.payload.status === 'rejected',
                'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300': props.payload.status === 'error' || props.payload.status === 'expired',
              }"
            >{{ statusLabel }}</span>
            <button
              type="button"
              class="flex h-8 w-8 items-center justify-center rounded-md opacity-70 transition hover:bg-black/5 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
              :aria-label="expanded ? '收起确认详情' : '展开确认详情'"
              :aria-expanded="expanded"
              @click.stop="toggleCard"
            >
              <svg class="h-4 w-4 transition-transform duration-200" :class="{ 'rotate-180': !expanded }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m19 15-7-7-7 7" />
              </svg>
            </button>
          </div>
        </div>

        <div v-show="expanded" :id="detailsId" :class="isCompact ? 'mt-2' : 'mt-3'">
          <div v-if="isCompact" class="space-y-2">
            <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
              <span class="opacity-60">风险等级</span>
              <span class="font-semibold">{{ display.riskLabel }}</span>
              <span class="opacity-30" aria-hidden="true">·</span>
              <span class="opacity-60">影响范围</span>
              <span class="font-semibold">{{ display.scopeLabel }} · 仅本次执行</span>
            </div>

            <div v-if="hasDetails" class="flex min-w-0 items-center gap-2 rounded-lg border border-current/15 bg-white/65 px-2.5 py-1.5 dark:bg-gray-950/30">
              <span class="shrink-0 text-[10px] font-semibold opacity-60">命令</span>
              <pre class="min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-[11px] leading-5">{{ display.commandText || display.parameterText }}</pre>
              <button
                type="button"
                class="min-h-8 shrink-0 rounded px-1.5 py-1 text-[10px] font-semibold transition hover:bg-black/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
                :aria-label="copied ? '命令已复制' : copyFailed ? '复制失败' : '复制命令'"
                @click="copyDetails"
              >
                {{ copied ? "已复制" : copyFailed ? "复制失败" : "复制" }}
              </button>
            </div>
          </div>

          <template v-else>
            <div class="grid gap-2 text-[11px] sm:grid-cols-2">
              <div class="rounded-lg border border-current/10 bg-white/45 px-3 py-2 dark:bg-black/10">
                <span class="block opacity-60">风险等级</span>
                <span class="mt-0.5 block font-semibold">{{ display.riskLabel }}</span>
              </div>
              <div class="rounded-lg border border-current/10 bg-white/45 px-3 py-2 dark:bg-black/10">
                <span class="block opacity-60">影响范围</span>
                <span class="mt-0.5 block font-semibold">{{ display.scopeLabel }}</span>
              </div>
            </div>

            <p class="mt-2 break-words leading-5 opacity-80">{{ display.impactDescription }}</p>

            <div v-if="hasDetails" class="mt-3 overflow-hidden rounded-lg border border-current/15 bg-white/65 dark:bg-gray-950/30">
            <div class="flex min-h-10 items-center gap-2 px-3 py-1">
              <button
                type="button"
                class="flex min-h-8 min-w-0 flex-1 items-center justify-between gap-3 py-1 text-left font-semibold transition hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-current"
                :aria-expanded="detailsExpanded"
                @click="toggleDetails"
              >
                <span>{{ detailLabel }}</span>
                <span class="flex items-center gap-2 text-[10px] font-normal opacity-65">
                  <span>{{ detailSummary }}</span>
                  <svg class="h-3.5 w-3.5 transition-transform" :class="{ 'rotate-180': detailsExpanded }" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m19 15-7-7-7 7" />
                  </svg>
                </span>
              </button>
              <button
                type="button"
                class="shrink-0 rounded px-1.5 py-1 text-[10px] font-semibold transition hover:bg-black/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
                :aria-label="copied ? '命令已复制' : copyFailed ? '复制失败' : '复制命令'"
                @click="copyDetails"
              >
                {{ copied ? "已复制" : copyFailed ? "复制失败" : "复制" }}
              </button>
            </div>
            <div v-show="detailsExpanded" class="border-t border-current/10 p-2">
              <pre class="max-h-56 overflow-auto whitespace-pre-wrap break-words rounded-md bg-gray-950/[0.04] p-2 font-mono text-[11px] leading-5 text-gray-700 dark:bg-white/[0.04] dark:text-gray-200">{{ display.commandText || display.parameterText }}</pre>
            </div>
            </div>
          </template>

          <div v-if="!isCompact || !isPending" class="mt-3 flex items-center gap-2" aria-live="polite">
            <span class="inline-flex h-4 w-4 shrink-0 items-center justify-center" :class="{ 'animate-spin': isSubmitting }" aria-hidden="true">
              <svg v-if="isSubmitting" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" />
                <path class="opacity-90" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V1C6.925 1 3 5.925 3 12h1Z" />
              </svg>
              <svg v-else-if="props.payload.status === 'approved'" class="h-4 w-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m5 13 4 4L19 7" />
              </svg>
            </span>
            <p class="leading-5 opacity-80">{{ statusMessage }}</p>
          </div>

          <div v-if="isPending" :class="isCompact ? 'mt-3' : 'mt-4'" class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              class="inline-flex min-h-[2.75rem] w-full items-center justify-center rounded-lg border border-current/20 bg-white/75 px-4 py-2 text-xs font-bold opacity-80 shadow-sm transition hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current disabled:cursor-not-allowed disabled:opacity-45 sm:w-auto"
              :disabled="locked"
              aria-label="拒绝执行本次工具调用"
              @click="submit(false)"
            >
              拒绝执行
            </button>
            <button
              type="button"
              class="inline-flex min-h-[2.75rem] w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-xs font-bold text-white shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-45 sm:w-auto"
              :class="display.riskTone === 'low' ? 'bg-sky-600 hover:bg-sky-700 focus-visible:ring-sky-600' : 'bg-amber-600 hover:bg-amber-700 focus-visible:ring-amber-600'"
              :disabled="locked"
              aria-label="仅本次允许执行工具调用"
              @click="submit(true)"
            >
              <svg v-if="!isSubmitting" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="m5 13 4 4L19 7" />
              </svg>
              {{ isSubmitting ? "正在提交确认…" : "本次允许执行" }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
