<script setup lang="ts">
defineProps<{
  visible: boolean;
  pendingReport: any | null;
  form: Record<string, any>;
  previewing: boolean;
  preview: Record<string, any> | null;
  usesMonthRange: (report: any | null) => boolean;
  usesDateRange: (report: any | null) => boolean;
  overlayClass?: string;
  overlayStyle?: Record<string, string>;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "execute"): void;
}>();
</script>

<template>
    <!-- Modal: Run Saved Report -->
    <teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-y-0 left-0 z-[250] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      :class="overlayClass"
      :style="overlayStyle"
      @click.self="emit('close')"
    >
      <div class="bg-white dark:bg-gray-800 w-full max-w-md rounded-2xl shadow-2xl overflow-hidden border border-gray-100 dark:border-gray-700">
        <div class="px-6 py-4 border-b border-gray-100 dark:border-gray-700 flex justify-between items-center bg-gray-50/50 dark:bg-gray-800/50">
          <div>
            <h3 class="text-base font-black text-gray-800 dark:text-gray-100 uppercase tracking-widest">运行固化报表</h3>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate max-w-[18rem]">{{ pendingReport?.title }}</p>
          </div>
          <button @click="emit('close')" class="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-colors text-gray-400">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div v-if="usesDateRange(pendingReport)">
            <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">日期范围</label>
            <select
              v-model="form.dateRange"
              class="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary text-gray-800 dark:text-gray-200"
            >
              <option value="today">今天</option>
              <option value="yesterday">昨天</option>
              <option value="last_7_days">最近 7 天</option>
              <option value="month_start_to_today">本月截至今天</option>
              <option value="year_start_to_today">今年（年初至今天）</option>
              <option value="custom_range">自定义日期</option>
            </select>
          </div>
          <div v-if="form.dateRange === 'custom_range'" class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">开始日期</label>
              <input v-model="form.startDate" type="date" class="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 text-sm text-gray-800 dark:text-gray-200" />
            </div>
            <div>
              <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">结束日期</label>
              <input v-model="form.endDate" type="date" class="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 text-sm text-gray-800 dark:text-gray-200" />
            </div>
          </div>
          <div v-if="usesMonthRange(pendingReport)">
            <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">月份范围</label>
            <select
              v-model="form.monthRange"
              class="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary text-gray-800 dark:text-gray-200"
            >
              <option value="last_6_completed_months">最近 6 个完整月</option>
              <option value="year_start_to_current_month">本年截至本月</option>
              <option value="custom_month_range">自定义月份</option>
            </select>
          </div>
          <div v-if="usesMonthRange(pendingReport) && form.monthRange === 'custom_month_range'" class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">开始月份</label>
              <input v-model="form.startMonth" type="month" class="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 text-sm text-gray-800 dark:text-gray-200" />
            </div>
            <div>
              <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">结束月份</label>
              <input v-model="form.endMonth" type="month" class="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 text-sm text-gray-800 dark:text-gray-200" />
            </div>
          </div>
          <div
            v-for="item in (pendingReport?.params_schema || []).filter((param: any) => !['date_range', 'month_range'].includes(String(param?.type || '')) && !['date_range', 'month_range'].includes(String(param?.name || '')) )"
            :key="item.name"
            class="space-y-1.5"
          >
            <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              {{ item.label || item.name }}
              <span v-if="item.required" class="text-red-500">*</span>
            </label>
            <select
              v-if="item.type === 'select'"
              v-model="form.customParams[item.name]"
              class="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800 focus:border-primary focus:outline-none dark:border-gray-700 dark:bg-gray-950 dark:text-gray-200"
            >
              <option v-for="option in (item.options || [])" :key="String(option)" :value="option">{{ option }}</option>
            </select>
            <input
              v-else
              v-model="form.customParams[item.name]"
              :type="item.type === 'number' ? 'number' : 'text'"
              class="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800 focus:border-primary focus:outline-none dark:border-gray-700 dark:bg-gray-950 dark:text-gray-200"
              :placeholder="item.type === 'number' ? '请输入数字' : `请输入${item.label || item.name}`"
            />
          </div>
          <p v-if="(pendingReport?.params_schema || []).some((item: any) => !['date_range', 'month_range'].includes(String(item?.type || '')) && !['date_range', 'month_range'].includes(String(item?.name || '')))" class="text-[11px] text-gray-400">
            参数配置会参与权限预检；请确认填写值属于业务允许范围。
          </p>
          <div class="flex items-center justify-between gap-3 p-3 rounded-xl border border-blue-100 dark:border-blue-900/40 bg-blue-50/40 dark:bg-blue-950/20">
            <span>
              <span class="block text-sm font-bold text-gray-800 dark:text-gray-100">执行并分析</span>
              <span class="block text-xs text-gray-500 dark:text-gray-400 mt-0.5">执行完成后将自动让 ChatBI 解读结果</span>
            </span>
          </div>
          <div class="rounded-xl border border-gray-100 dark:border-gray-700 bg-gray-50/60 dark:bg-gray-950/40 overflow-hidden min-h-[10.5rem]">
            <div class="px-3 py-2 flex items-center justify-between border-b border-gray-100 dark:border-gray-800">
              <span class="text-xs font-black text-gray-600 dark:text-gray-300">实际执行 SQL</span>
              <span
                class="text-[10px] font-bold px-2 py-0.5 rounded"
                :class="previewing ? 'bg-gray-100 text-gray-500' : preview?.permission_status === 'denied' ? 'bg-red-50 text-red-600' : preview?.permission_status === 'allowed' ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'"
              >
                {{ previewing ? '预检中' : preview?.permission_status === 'denied' ? '无权限' : preview?.permission_status === 'allowed' ? '可运行' : '待校验' }}
              </span>
            </div>
            <div v-if="previewing" class="px-3 py-4 text-xs text-gray-400">正在生成运行预览...</div>
            <pre v-else class="max-h-44 overflow-auto px-3 py-2 text-[11px] font-mono leading-relaxed text-gray-600 dark:text-gray-300 whitespace-pre-wrap">{{ preview?.rendered_sql || pendingReport?.sql_content || '' }}</pre>
            <p v-if="preview?.permission_message" class="px-3 pb-3 text-[11px] text-red-500">{{ preview.permission_message }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-100 dark:border-gray-700 flex justify-end space-x-3 bg-gray-50/50 dark:bg-gray-800/50">
          <button @click="emit('close')" class="px-4 py-2 text-xs font-bold text-gray-500 border border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
            取消
          </button>
          <button
            @click="emit('execute')"
            :disabled="previewing || !preview || preview?.can_run === false"
            class="px-4 py-2 text-xs font-bold text-white bg-primary rounded-xl hover:bg-primary-hover active:bg-primary-active disabled:opacity-50 transition-colors"
          >
            开始运行
          </button>
        </div>
      </div>
    </div>
    </teleport>

</template>
