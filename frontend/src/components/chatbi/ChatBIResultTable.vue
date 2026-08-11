<template>
  <div
    v-if="table && table.columns?.length && table.rows?.length"
    :class="
      embedded
        ? 'border-t border-gray-200/80 dark:border-gray-700/80'
        : 'mt-3 overflow-hidden rounded-xl border border-gray-200 bg-gray-50/80 text-xs dark:border-gray-700 dark:bg-gray-800/40'
    "
  >
    <button
      type="button"
      class="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-white/50 dark:hover:bg-gray-900/20"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <span class="min-w-0">
        <span class="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 font-semibold text-gray-700 dark:text-gray-200">
          <span class="truncate">查询结果明细 · {{ totalCount }} 行</span>
          <span
            v-if="sampleNotice"
            class="rounded-full bg-gray-200/70 px-2 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-gray-700/80 dark:text-gray-300"
            :title="sampleNotice"
          >
            AI 基于前 {{ analysisScope?.model_row_count }}/{{ analysisScope?.total_row_count }} 行样例
          </span>
        </span>
        <span v-if="table.truncated" class="mt-0.5 block text-[10px] font-normal text-gray-400">
          已嵌入前 {{ table.embedded_row_count }} 行
        </span>
      </span>
      <span class="flex shrink-0 items-center gap-1 text-[11px] font-semibold text-primary">
        <span>{{ expanded ? "收起" : "展开" }}</span>
        <svg
          class="h-3.5 w-3.5 transition-transform"
          :class="expanded ? 'rotate-180' : ''"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </span>
    </button>

    <div v-if="expanded" class="border-t border-gray-200/80 bg-white dark:border-gray-700/80 dark:bg-gray-900/30">
      <p
        v-if="sampleNotice"
        class="border-b border-gray-100 px-3 py-2 text-[11px] leading-relaxed text-gray-500 dark:border-gray-800 dark:text-gray-400"
      >
        {{ sampleNotice }}
      </p>
      <div
        v-if="pageCount > 1"
        class="flex items-center justify-end gap-2 border-b border-gray-100 px-3 py-1.5 text-[11px] text-gray-500 dark:border-gray-800"
      >
        <button
          type="button"
          class="rounded px-2 py-1 font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40"
          :class="page > 1 ? 'text-primary hover:bg-primary/5' : ''"
          :disabled="page <= 1"
          @click.stop="page = Math.max(1, page - 1)"
        >
          上一页
        </button>
        <span class="tabular-nums">{{ page }} / {{ pageCount }}</span>
        <button
          type="button"
          class="rounded px-2 py-1 font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40"
          :class="page < pageCount ? 'text-primary hover:bg-primary/5' : ''"
          :disabled="page >= pageCount"
          @click.stop="page = Math.min(pageCount, page + 1)"
        >
          下一页
        </button>
      </div>
      <div class="max-h-80 overflow-auto">
        <table class="min-w-full border-collapse text-left">
          <thead class="sticky top-0 z-[1] bg-gray-50 dark:bg-gray-800">
            <tr>
              <th
                v-for="col in table.columns"
                :key="col"
                class="whitespace-nowrap border-b border-gray-200 px-3 py-2 font-bold text-gray-700 dark:border-gray-700 dark:text-gray-200"
              >
                {{ col }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, rowIndex) in pageRows"
              :key="`${page}-${rowIndex}`"
              class="odd:bg-white even:bg-gray-50/70 dark:odd:bg-transparent dark:even:bg-gray-800/30"
            >
              <td
                v-for="(cell, cellIndex) in row"
                :key="cellIndex"
                class="max-w-[16rem] truncate border-b border-gray-100 px-3 py-1.5 text-gray-700 dark:border-gray-800 dark:text-gray-200"
                :title="cellTitle(cell)"
              >
                {{ formatCell(cell) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { ChatBIAnalysisScope, ChatBIResultTable } from "@/types/chatbiInsight";

const props = withDefaults(
  defineProps<{
    table?: ChatBIResultTable | null;
    analysisScope?: ChatBIAnalysisScope | null;
    embedded?: boolean;
  }>(),
  { embedded: false },
);

/** 默认折叠：查数成功显示摘要条；用户可一键展开明细。 */
const expanded = ref(false);
const page = ref(1);

const sampleNotice = computed(() => {
  const scope = props.analysisScope;
  if (!scope || scope.mode !== "sample") return "";
  const notice = String(scope.user_notice || "").trim();
  if (notice) return notice;
  return (
    `AI 解读基于全部 ${scope.total_row_count} 行中的前 ${scope.model_row_count} 行样例，` +
    "并非逐行全量分析；完整明细见下方表格。"
  );
});

const pageSize = computed(() => {
  const size = Number(props.table?.page_size || 50);
  return Number.isFinite(size) && size > 0 ? Math.floor(size) : 50;
});

const embeddedRows = computed(() => {
  const rows = props.table?.rows;
  return Array.isArray(rows) ? rows : [];
});

const totalCount = computed(() => {
  const total = Number(props.table?.total_row_count);
  if (Number.isFinite(total) && total > 0) return total;
  return embeddedRows.value.length;
});

const pageCount = computed(() => Math.max(1, Math.ceil(embeddedRows.value.length / pageSize.value)));

const pageRows = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return embeddedRows.value.slice(start, start + pageSize.value);
});

watch(
  () => props.table,
  () => {
    page.value = 1;
    expanded.value = false;
  },
);

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function cellTitle(value: unknown): string {
  return formatCell(value);
}
</script>
