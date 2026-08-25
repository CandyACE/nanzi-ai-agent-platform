<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <h2 class="text-base font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <span>固化报表</span>
          <span v-if="!compact" class="text-xs font-normal text-gray-400">已沉淀与手工开发的标准化 SQL 报表</span>
        </h2>
        <button
          v-if="!compact"
          type="button"
          class="flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 bg-white text-blue-600 shadow-2xs hover:border-blue-300 hover:bg-blue-50 cursor-pointer"
          title="固化报表使用指南与规范"
          @click="emit('open-specs')"
        >
          <span class="text-xs font-bold">?</span>
        </button>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="option in visibleFilters"
            :key="option.value"
            type="button"
            class="rounded-lg px-2.5 py-1 text-xs font-medium transition cursor-pointer"
            :class="activeFilter === option.value ? 'bg-blue-600 text-white shadow-2xs' : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400'"
            @click="setFilter(option.value)"
          >
            {{ option.label }} {{ option.value === 'all' ? reports.length : (summary[option.value] || '') }}
          </button>
        </div>

        <!-- 非 compact 模式下的新建主操作按钮 -->
        <button
          v-if="!compact"
          type="button"
          class="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm shadow-blue-500/20 transition-all cursor-pointer"
          @click="emit('create-report')"
        >
          <span>➕ 新建固化报表</span>
        </button>
      </div>
    </div>

    <div v-if="filteredReports.length" class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      <button
        v-for="report in filteredReports"
        :key="report.id"
        type="button"
        class="min-h-[116px] rounded-2xl border border-gray-100 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md dark:border-gray-800 dark:bg-gray-900 group cursor-pointer"
        @click="emit('open-report', report)"
      >
        <div class="flex items-start justify-between gap-2">
          <strong class="line-clamp-2 text-sm text-gray-900 dark:text-gray-100 group-hover:text-blue-600 transition-colors">
            {{ report.title }}
          </strong>
          <span
            v-if="report.pinned || !!report.pinned_at"
            class="shrink-0 text-amber-500 text-xs font-bold"
            title="已置顶"
          >
            📌
          </span>
        </div>
        <div class="mt-1 text-xs text-gray-400">
          {{ report.is_owner ? '我的报表' : `共享自 ${report.owner_name || '其他用户'}` }}
        </div>
        <div class="mt-5 flex items-center justify-between gap-2 text-xs">
          <span :class="report.last_error ? 'text-red-500' : 'text-emerald-500'">
            {{ report.last_error ? '最近运行失败' : report.subscription_status ? '订阅运行中' : '可运行' }}
          </span>
          <span class="text-gray-400">{{ formatTime(report.last_run_at) }}</span>
        </div>
      </button>
    </div>
    <div
      v-else
      class="rounded-2xl border border-dashed border-gray-200 p-8 text-center text-sm text-gray-400 dark:border-gray-800 space-y-2"
    >
      <p>当前分类下还没有固化报表</p>
      <p v-if="!compact" class="text-xs text-gray-500">
        您可以点击右上角「➕ 新建固化报表」手工录入 SQL，或在 ChatBI 智能对话查数成功后点击「添加固化报表」
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { DataPortalHomePayload, DataPortalReportFilter, DataPortalReportItem } from "@/types/dataPortal";

const props = withDefaults(
  defineProps<{
    reports: DataPortalReportItem[];
    summary: DataPortalHomePayload["report_summary"];
    compact?: boolean;
    initialFilter?: DataPortalReportFilter;
  }>(),
  { compact: false, initialFilter: "all" }
);

const emit = defineEmits<{
  (event: "open-report", report: DataPortalReportItem): void;
  (event: "filter-change", filter: DataPortalReportFilter): void;
  (event: "create-report"): void;
  (event: "open-specs"): void;
}>();

const activeFilter = ref<DataPortalReportFilter>(props.compact ? "subscribed" : props.initialFilter);
const filters: Array<{ value: DataPortalReportFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "subscribed", label: "已订阅" },
  { value: "pinned", label: "置顶" },
  { value: "favorite", label: "收藏" },
  { value: "shared", label: "共享给我" },
  { value: "recent", label: "最近运行" },
];

const visibleFilters = computed(() => (props.compact ? filters.filter((item) => item.value !== "all") : filters));
const filteredReports = computed(() => {
  const reports = props.reports.filter((report) => {
    if (activeFilter.value === "all") return true;
    if (activeFilter.value === "subscribed") return !!report.subscription_status;
    if (activeFilter.value === "pinned") return report.pinned || !!report.pinned_at;
    if (activeFilter.value === "favorite") return report.is_favorite;
    if (activeFilter.value === "shared") return !report.is_owner;
    return !!report.last_run_at;
  });
  return props.compact ? reports.slice(0, 6) : reports;
});

const setFilter = (filter: DataPortalReportFilter) => {
  activeFilter.value = filter;
  emit("filter-change", filter);
};

watch(
  () => props.initialFilter,
  (filter) => {
    if (!props.compact) activeFilter.value = filter;
  }
);

const formatTime = (value?: string | null) =>
  value ? new Date(value).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" }) : "尚未运行";
</script>
