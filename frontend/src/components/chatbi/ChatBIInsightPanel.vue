<template>
  <div
    v-if="visible"
    class="mt-3 mb-3 border-t border-gray-100 pt-3 dark:border-gray-700/50"
  >
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      <span
        v-if="meta"
        class="inline-flex items-center gap-1 text-emerald-600/80 dark:text-emerald-400/80"
      >
        <span class="text-[10px]">✓</span>
        <span>查询成功 · {{ resultCountLabel }}</span>
      </span>
      <div class="flex min-w-0 flex-1 items-center gap-1.5">
        <svg
          class="h-3.5 w-3.5 shrink-0 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5S19.832 5.477 21 6.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
          />
        </svg>
        <div class="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            type="button"
            class="group/tab inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider transition-colors"
            :class="
              activeTab === tab.id
                ? 'text-gray-600 dark:text-gray-200'
                : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'
            "
            @click="toggleTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </div>
        <span
          v-if="sampleChip"
          class="text-[10px] text-gray-400 dark:text-gray-500"
          :title="sampleNotice"
        >
          {{ sampleChip }}
        </span>
        <svg
          class="ml-auto h-3.5 w-3.5 shrink-0 text-gray-400 transition-transform duration-200"
          :class="{ 'rotate-180': !!activeTab }"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </div>

    <div v-if="activeTab === 'citations' && hasCitations" class="mt-2">
      <div class="flex flex-wrap gap-2 py-1">
        <button
          v-for="(cite, cIdx) in citations"
          :key="cIdx"
          type="button"
          class="citation-chip group/cite relative flex max-w-full items-center space-x-2 overflow-hidden rounded-lg px-2.5 py-1.5 transition-all"
          :class="
            cite.similarity && cite.similarity < 0.5
              ? 'border border-amber-200/80 bg-amber-50/80 hover:border-amber-400/60 dark:border-amber-700/50 dark:bg-amber-900/20'
              : 'border border-gray-100 bg-gray-50 hover:border-primary/40 dark:border-gray-700 dark:bg-gray-800/80 dark:hover:border-primary/40'
          "
          @click.stop="emitOpenCitation(cite, $event)"
        >
          <svg class="h-3.5 w-3.5 shrink-0 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span
            class="max-w-[120px] truncate text-[11px] font-medium text-gray-600 dark:text-gray-300 sm:max-w-[150px]"
            :title="cite.doc_name"
          >
            {{ cite.doc_name }}
          </span>
          <span
            v-if="cite.similarity"
            class="rounded px-1 font-mono text-[9px]"
            :class="
              cite.similarity < 0.5
                ? 'bg-amber-100/80 text-amber-600 dark:bg-amber-900/40 dark:text-amber-400'
                : 'bg-gray-100 text-gray-400 dark:bg-gray-700'
            "
            :title="cite.similarity < 0.5 ? '相似度较低，请结合原文核对' : undefined"
          >
            {{ (cite.similarity * 100).toFixed(0) }}%
          </span>
        </button>
      </div>
    </div>

    <div v-else-if="activeTab === 'table' && hasTable" class="mt-2">
      <p v-if="sampleNotice" class="mb-1.5 text-[10px] leading-relaxed text-gray-400 dark:text-gray-500">
        {{ sampleNotice }}
      </p>
      <div class="mb-1 flex items-center justify-between gap-2 text-[10px] text-gray-400">
        <button
          type="button"
          class="inline-flex items-center gap-1 text-gray-400 transition-colors hover:text-primary"
          title="导出全部嵌入行的 Markdown 表格"
          @click="exportMarkdown"
        >
          <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>导出 Markdown</span>
        </button>
        <div v-if="pageCount > 1" class="flex items-center gap-2">
          <button
            type="button"
            class="disabled:opacity-40"
            :disabled="page <= 1"
            @click="page = Math.max(1, page - 1)"
          >
            上一页
          </button>
          <span class="tabular-nums">{{ page }} / {{ pageCount }}</span>
          <button
            type="button"
            class="disabled:opacity-40"
            :disabled="page >= pageCount"
            @click="page = Math.min(pageCount, page + 1)"
          >
            下一页
          </button>
        </div>
      </div>
      <div class="max-h-72 overflow-auto rounded-md bg-gray-50/60 dark:bg-gray-900/20">
        <table class="min-w-full border-collapse text-left text-[11px]">
          <thead class="sticky top-0 z-[1] bg-gray-50/95 dark:bg-gray-900/80">
            <tr>
              <th
                v-for="col in meta!.table!.columns"
                :key="col"
                class="whitespace-nowrap px-2.5 py-1.5 font-medium text-gray-500 dark:text-gray-400"
              >
                {{ col }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, rowIndex) in pageRows"
              :key="`${page}-${rowIndex}`"
              class="odd:bg-transparent even:bg-white/40 dark:even:bg-white/[0.02]"
            >
              <td
                v-for="(cell, cellIndex) in row"
                :key="cellIndex"
                class="max-w-[14rem] truncate px-2.5 py-1 text-gray-600 dark:text-gray-300"
                :title="formatCell(cell)"
              >
                {{ formatCell(cell) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div
      v-else-if="activeTab === 'evidence' && meta"
      class="mt-2 space-y-2 text-[11px] leading-relaxed text-gray-500 dark:text-gray-400"
    >
      <div class="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        <div>证据状态：{{ evidenceStatusLabel }}</div>
        <div class="break-all">来源：{{ meta.evidence?.source_ref || "未识别" }}</div>
        <div>观测时间：{{ formatEvidenceTime(meta.evidence?.observed_at) }}</div>
        <div>数据截至：{{ formatEvidenceTime(meta.evidence?.source_as_of) }}</div>
        <div>时效：{{ freshnessLabel }}</div>
        <div>执行：{{ executionLabel }}</div>
      </div>
      <div v-if="meta.sources?.length">
        <div v-for="(source, index) in meta.sources" :key="index">
          {{ source.dataset_name || "授权数据集" }}
          <span class="text-gray-400">· {{ source.tables.map((item) => item.physical_name).join("、") }}</span>
        </div>
      </div>
      <div v-if="meta.permission?.row_filter_applied">
        {{ meta.permission.message || "已按你的数据权限自动过滤结果" }}
        <span v-if="meta.permission.rule_count">（{{ meta.permission.rule_count }} 条规则）</span>
      </div>
      <div v-if="meta.final_sql">
        <button type="button" class="text-gray-500 underline-offset-2 hover:underline" @click="showSql = !showSql">
          {{ showSql ? "收起 SQL" : "查看 SQL" }}
        </button>
        <pre
          v-if="showSql"
          class="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded-md bg-gray-50/80 p-2 font-mono text-[10px] text-gray-600 dark:bg-gray-900/40 dark:text-gray-300"
        >{{ meta.final_sql }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { ChatBIInsightMeta } from "@/types/chatbiInsight";
import { exportChatBIResultMarkdown } from "@/utils/chatbiResultExport";

const props = defineProps<{
  meta?: ChatBIInsightMeta | null;
  citations?: any[] | null;
}>();

const emit = defineEmits<{
  (e: "open-citation", payload: { citation: any; event: MouseEvent }): void;
}>();

type TabId = "citations" | "table" | "evidence" | null;

const activeTab = ref<TabId>(null);
const page = ref(1);
const showSql = ref(false);

const citations = computed(() => (Array.isArray(props.citations) ? props.citations : []));
const hasCitations = computed(() => citations.value.length > 0);
const hasTable = computed(
  () => !!(props.meta?.table?.columns?.length && props.meta?.table?.rows?.length),
);
const visible = computed(() => !!(props.meta || hasCitations.value));

const tabs = computed(() => {
  const items: Array<{ id: Exclude<TabId, null>; label: string }> = [];
  if (hasCitations.value) {
    items.push({ id: "citations", label: `引用来源 (${citations.value.length})` });
  }
  if (hasTable.value) items.push({ id: "table", label: "明细" });
  if (props.meta) items.push({ id: "evidence", label: "依据" });
  return items;
});

const exactTotalCount = computed<number | null>(() => {
  const executionTotal = props.meta?.execution?.total_row_count;
  if (typeof executionTotal === "number" && Number.isFinite(executionTotal)) return executionTotal;
  const tableTotal = props.meta?.table?.total_row_count;
  return typeof tableTotal === "number" && Number.isFinite(tableTotal) ? tableTotal : null;
});

const returnedRowCount = computed(() => {
  const returned = props.meta?.execution?.returned_row_count;
  if (typeof returned === "number" && Number.isFinite(returned)) return returned;
  const executionRows = props.meta?.execution?.row_count;
  if (typeof executionRows === "number" && Number.isFinite(executionRows)) return executionRows;
  return embeddedRows.value.length;
});

const resultCountLabel = computed(() => {
  if (exactTotalCount.value !== null) {
    const total = formatCount(exactTotalCount.value);
    const returned = formatCount(returnedRowCount.value);
    const truncated = props.meta?.execution?.truncated ?? props.meta?.table?.truncated;
    return truncated ? `匹配总数 ${total} 条 · 已返回 ${returned} 行` : `匹配总数 ${total} 条`;
  }
  return `已返回 ${formatCount(returnedRowCount.value)} 行 · 总数未统计`;
});

const sampleNotice = computed(() => {
  const scope = props.meta?.analysis_scope;
  if (!scope || scope.mode !== "sample") return "";
  const totalLabel = scope.total_row_count == null ? "总数未知" : `${scope.total_row_count} 行`;
  const basis = scope.total_row_count == null
    ? `已返回 ${scope.model_row_count} 行`
    : `全部 ${totalLabel}中的前 ${scope.model_row_count} 行`;
  return (
    String(scope.user_notice || "").trim() ||
    `AI 解读基于${basis}样例${scope.total_row_count == null ? "，数据库总数未统计" : "，并非逐行全量分析"}。`
  );
});

const sampleChip = computed(() => {
  const scope = props.meta?.analysis_scope;
  if (!scope || scope.mode !== "sample") return "";
  return `AI 样例 ${scope.model_row_count}/${scope.total_row_count == null ? "总数未知" : scope.total_row_count}`;
});

const pageSize = computed(() => {
  const size = Number(props.meta?.table?.page_size || 50);
  return Number.isFinite(size) && size > 0 ? Math.floor(size) : 50;
});

const embeddedRows = computed(() => {
  const rows = props.meta?.table?.rows;
  return Array.isArray(rows) ? rows : [];
});

const pageCount = computed(() => Math.max(1, Math.ceil(embeddedRows.value.length / pageSize.value)));

const pageRows = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return embeddedRows.value.slice(start, start + pageSize.value);
});

const evidenceStatusLabel = computed(() => {
  const labels: Record<string, string> = {
    success_non_empty: "查询成功 · 有数据",
    success_empty: "查询成功 · 空结果",
    failed: "查询失败",
    unavailable: "数据源不可用",
    denied: "访问被拒绝",
    unknown: "未知",
  };
  return labels[props.meta?.evidence?.result_status || "unknown"] || props.meta?.evidence?.result_status || "未知";
});

const freshnessLabel = computed(() => {
  const labels: Record<string, string> = {
    realtime: "实时",
    dynamic: "动态",
    historical: "历史",
    reuse_previous: "复用上一结果",
    static: "静态",
    unknown: "未知",
  };
  const value = props.meta?.evidence?.freshness || "unknown";
  return labels[value] || value;
});

const executionLabel = computed(() => {
  if (!props.meta) return "";
  if (props.meta.execution.mode === "federated") return "跨数据集联邦查询";
  if (props.meta.execution.mode === "repaired") return `修复后成功（${props.meta.execution.repair_count || 1} 次）`;
  return "SQL 直接执行成功";
});

watch(
  () => [props.meta?.result_id, props.meta?.table, citations.value.length] as const,
  () => {
    activeTab.value = null;
    page.value = 1;
    showSql.value = false;
  },
);

function toggleTab(tabId: Exclude<TabId, null>) {
  activeTab.value = activeTab.value === tabId ? null : tabId;
}

function exportMarkdown() {
  if (!props.meta?.table?.columns?.length) return;
  exportChatBIResultMarkdown({
    columns: props.meta.table.columns,
    rows: embeddedRows.value,
    totalRowCount: Number(props.meta.table.total_row_count || embeddedRows.value.length),
    resultId: props.meta.result_id,
    sampleNotice: sampleNotice.value || undefined,
  });
}

function emitOpenCitation(citation: any, event: MouseEvent) {
  emit("open-citation", { citation, event });
}

function formatEvidenceTime(value?: string | null) {
  if (!value) return "未提供";
  return value.replace("T", " ").replace(/\.\d{3,6}(?=[+-]\d{2}:?\d{2}|Z$)/, "");
}

function formatCount(value: number): string {
  return value.toLocaleString("zh-CN");
}

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
</script>
