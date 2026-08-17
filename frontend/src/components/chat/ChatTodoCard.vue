<template>
  <div
    v-if="todo && !closed"
    class="mb-1 w-full min-w-0 max-w-[42rem] rounded-xl border border-violet-200/80 bg-violet-50/70 px-3 py-2 text-[12px] leading-5 lg:max-w-[48rem] 2xl:max-w-[52rem] dark:border-violet-800/50 dark:bg-violet-950/20"
  >
    <div class="flex items-center gap-1">
      <button
        type="button"
        class="flex min-w-0 flex-1 items-center gap-2 text-left font-semibold text-violet-700 dark:text-violet-300"
        :aria-expanded="expanded"
        :aria-label="expanded ? '折叠任务清单' : '展开任务清单'"
        @click="toggleExpanded"
      >
        <span aria-hidden="true">📝</span>
        <span class="min-w-0 flex-1 truncate">{{ todo.title }}</span>
        <span class="shrink-0 text-[10px] font-normal text-violet-500 dark:text-violet-400">
          {{ todo.counts.completed }}/{{ todo.todos.length }} 已完成
        </span>
        <svg
          class="h-3.5 w-3.5 shrink-0 transition-transform"
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
        class="flex h-5 w-5 shrink-0 items-center justify-center rounded text-sm font-normal text-violet-400 hover:bg-violet-100 hover:text-violet-700 dark:text-violet-500 dark:hover:bg-violet-900/40 dark:hover:text-violet-300"
        aria-label="关闭任务清单"
        title="关闭任务清单"
        @click="closeCard"
      >
        ×
      </button>
    </div>
    <div v-if="expanded" class="mt-1.5 space-y-0.5">
      <div
        v-for="item in todo.todos"
        :key="item.content"
        class="flex items-start gap-2"
        :class="item.status === 'completed' ? 'text-violet-400 dark:text-violet-500' : 'text-violet-700 dark:text-violet-300'"
      >
        <span class="mt-0.5 w-3 shrink-0 text-center" aria-hidden="true">
          {{ item.status === 'completed' ? '✓' : item.status === 'in_progress' ? '⟳' : '○' }}
        </span>
        <span class="min-w-0 flex-1 break-words" :class="item.status === 'completed' ? 'line-through' : ''">
          {{ item.content }}
        </span>
        <span v-if="item.status === 'in_progress'" class="shrink-0 text-[10px]">进行中</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
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

function toggleExpanded(): void {
  expanded.value = !expanded.value;
  autoCollapsed.value = false;
}

function closeCard(): void {
  closed.value = true;
  autoCollapsed.value = false;
}

watch(
  todo,
  (next) => {
    if (!next) return;
    if (next.todos.length > 0 && next.counts.completed === next.todos.length) {
      expanded.value = false;
      autoCollapsed.value = true;
    } else if (autoCollapsed.value) {
      expanded.value = true;
      autoCollapsed.value = false;
    }
  },
  { deep: true, immediate: true },
);
</script>
