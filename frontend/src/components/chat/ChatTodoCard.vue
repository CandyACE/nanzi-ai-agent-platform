<template>
  <transition
    enter-active-class="transition-all duration-200 ease-out"
    enter-from-class="opacity-0 -translate-y-1 scale-98"
    enter-to-class="opacity-100 translate-y-0 scale-100"
    leave-active-class="transition-all duration-300 ease-in"
    leave-from-class="opacity-100 translate-y-0 scale-100"
    leave-to-class="opacity-0 -translate-y-1 scale-98"
  >
    <div
      v-if="todo && !closed"
      class="w-full min-w-0 rounded-xl border border-slate-200/80 bg-slate-50/90 px-3.5 py-2 text-[12px] leading-5 shadow-xs backdrop-blur-xs transition-all dark:border-slate-800/80 dark:bg-slate-900/90"
    >
      <div class="flex items-center gap-1.5">
        <button
          type="button"
          class="group flex min-w-0 flex-1 items-center gap-2 text-left font-medium text-slate-800 hover:text-slate-950 dark:text-slate-200 dark:hover:text-white"
          :aria-expanded="expanded"
          :aria-label="expanded ? '折叠任务清单' : '展开任务清单'"
          @click="toggleExpanded"
        >
          <span class="text-sm" aria-hidden="true">📋</span>
          <span class="min-w-0 flex-1 truncate font-semibold text-slate-800 dark:text-slate-100">{{ todo.title }}</span>
          <span
            class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium border"
            :class="todo.counts.completed === todo.todos.length
              ? 'border-emerald-200/80 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/40 dark:text-emerald-300'
              : 'border-blue-200/80 bg-blue-50 text-blue-700 dark:border-blue-900/40 dark:bg-blue-950/40 dark:text-blue-300'"
          >
            {{ todo.counts.completed }}/{{ todo.todos.length }} 已完成
          </span>
          <svg
            class="h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform group-hover:text-slate-600 dark:group-hover:text-slate-300"
            :class="{ 'rotate-180': expanded }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m19 9-7 7-7-7" />
          </svg>
        </button>
        <button
          type="button"
          class="flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-200/60 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          aria-label="关闭任务清单"
          title="关闭任务清单"
          @click="closeCard"
        >
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div v-if="expanded" class="mt-2 space-y-1 border-t border-slate-200/60 pt-1.5 dark:border-slate-800/60">
        <div
          v-for="item in todo.todos"
          :key="item.content"
          class="flex items-start gap-2 text-[11px] leading-relaxed transition-colors"
          :class="{
            'text-slate-400 dark:text-slate-500': item.status === 'completed',
            'font-medium text-slate-800 dark:text-slate-100': item.status === 'in_progress',
            'text-slate-500 dark:text-slate-400': item.status === 'pending',
          }"
        >
          <span class="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center text-center" aria-hidden="true">
            <!-- 已完成：绿色勾选 -->
            <svg v-if="item.status === 'completed'" class="h-3.5 w-3.5 text-emerald-500 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="m5 13 4 4L19 7" />
            </svg>
            <!-- 进行中：蓝色旋转图标 -->
            <svg v-else-if="item.status === 'in_progress'" class="h-3.5 w-3.5 animate-spin text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <!-- 待开始：柔和浅灰圆圈 -->
            <svg v-else class="h-3 w-3 text-slate-300 dark:text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="9" stroke-width="2" />
            </svg>
          </span>
          <span class="min-w-0 flex-1 break-words" :class="item.status === 'completed' ? 'line-through decoration-slate-300 dark:decoration-slate-600' : ''">
            {{ item.content }}
          </span>
          <span
            v-if="item.status === 'in_progress'"
            class="shrink-0 rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600 dark:bg-blue-950/60 dark:text-blue-400"
          >
            进行中
          </span>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import type { ProcessTimelineItem, ProcessTimelineTodoItem } from "@/utils/processTimeline";

const props = defineProps<{
  timeline?: ProcessTimelineItem[];
}>();

const todo = computed<ProcessTimelineTodoItem | undefined>(() =>
  [...(props.timeline || [])].reverse().find((item): item is ProcessTimelineTodoItem => item.kind === "todo"),
);

const expanded = ref(true);
const closed = ref(false);
const autoCollapsed = ref(false);
let autoDismissTimer: ReturnType<typeof setTimeout> | null = null;

function clearAutoDismissTimer(): void {
  if (autoDismissTimer) {
    clearTimeout(autoDismissTimer);
    autoDismissTimer = null;
  }
}

function toggleExpanded(): void {
  expanded.value = !expanded.value;
  autoCollapsed.value = false;
  // 手动展开时取消自动淡出
  if (expanded.value) {
    clearAutoDismissTimer();
  }
}

function closeCard(): void {
  clearAutoDismissTimer();
  closed.value = true;
  autoCollapsed.value = false;
}

watch(
  todo,
  (next, prev) => {
    if (!next) return;
    if (next.id !== prev?.id) {
      closed.value = false;
      clearAutoDismissTimer();
    }
    const isAllCompleted = next.todos.length > 0 && next.counts.completed === next.todos.length;
    if (isAllCompleted) {
      expanded.value = false;
      autoCollapsed.value = true;
      // 方案 B：全部完成后先折叠为单行，停留 2.5 秒后自动淡出隐藏
      clearAutoDismissTimer();
      autoDismissTimer = setTimeout(() => {
        closed.value = true;
      }, 2500);
    } else {
      clearAutoDismissTimer();
      if (autoCollapsed.value) {
        expanded.value = true;
        autoCollapsed.value = false;
      }
    }
  },
  { deep: true, immediate: true },
);

onUnmounted(() => {
  clearAutoDismissTimer();
});
</script>
