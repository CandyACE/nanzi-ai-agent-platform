<script setup lang="ts">
defineProps<{
  visible: boolean;
  form: Record<string, any>;
  editing: boolean;
  saving: boolean;
  overlayClass?: string;
  overlayStyle?: Record<string, string>;
  scrollbarVariant?: "embed" | "debug";
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "submit"): void;
}>();
</script>

<template>
    <!-- Modal: Save Report -->
    <teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-y-0 left-0 z-[250] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      :class="overlayClass"
      :style="overlayStyle"
      @click.self="emit('close')"
    >
      <div
        class="bg-white dark:bg-gray-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-gray-100 dark:border-gray-700"
      >
        <!-- Header -->
        <div class="px-6 py-4 border-b border-gray-100 dark:border-gray-700 flex justify-between items-center bg-gray-50/50 dark:bg-gray-800/50">
          <div class="flex items-center space-x-2">
            <div class="p-1.5 bg-primary/10 rounded-lg text-primary">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v2a2 2 0 01-2 2H7a2 2 0 01-2-2V5zM12 9v12m-3-3l3 3 3-3" />
              </svg>
            </div>
            <h3 class="text-base font-black text-gray-800 dark:text-gray-100 uppercase tracking-widest">{{ editing ? '编辑固化 SQL 报表' : '沉淀为固化报表' }}</h3>
          </div>
          <button @click="emit('close')" class="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-colors text-gray-400">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <!-- Body -->
        <div
          class="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar max-h-[60vh]"
          :class="{ 'custom-scrollbar-embed': scrollbarVariant === 'embed' }"
        >
          <div>
            <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">报表名称 <span class="text-red-500">*</span></label>
            <input
              v-model="form.title"
              type="text"
              placeholder="请输入自定义报表名称"
              class="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-gray-800 dark:text-gray-200"
            />
          </div>
          <div>
            <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">报表描述</label>
            <textarea
              v-model="form.description"
              rows="2"
              placeholder="说明这个报表适合回答什么业务问题"
              class="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-gray-800 dark:text-gray-200 resize-none"
            />
          </div>
          <div>
            <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">标签</label>
            <input
              v-model="form.tags_input"
              type="text"
              placeholder="例如：经营分析, 订单, 月报"
              class="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50 dark:bg-gray-950 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-gray-800 dark:text-gray-200"
            />
          </div>

          <div v-if="form.original_query">
            <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">原始提问</label>
            <div class="px-3 py-2 border border-gray-100 dark:border-gray-800 rounded-xl bg-gray-50 dark:bg-gray-900/50 text-xs text-gray-600 dark:text-gray-400 break-all select-all font-mono leading-relaxed max-h-20 overflow-y-auto">
              {{ form.original_query }}
            </div>
          </div>

          <div>
            <label class="block text-xs font-black text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">SQL 语句预览</label>
            <pre class="px-3 py-2 border border-gray-100 dark:border-gray-800 rounded-xl bg-gray-50 dark:bg-gray-900/50 text-xs text-gray-600 dark:text-gray-400 break-all select-all font-mono leading-relaxed overflow-x-auto max-h-40 overflow-y-auto">{{ form.sql_content }}</pre>
            <span class="text-[10px] text-gray-400 mt-1 block">提示：系统将自动反查关联的数据集与数据源以保证直连执行时能够顺利通过权限安全校验。</span>
          </div>
          <div
            v-if="form.mode === 'param_sql'"
            class="p-3 rounded-xl border border-blue-100 dark:border-blue-900/40 bg-blue-50/50 dark:bg-blue-950/20 text-xs text-blue-700 dark:text-blue-300 leading-relaxed"
          >
            已识别到固定日期条件，将保存为动态日期报表。后续运行时可选择今天、昨天、最近 7 天、本月、今年或自定义日期范围。
          </div>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-gray-100 dark:border-gray-700 flex justify-end space-x-3 bg-gray-50/50 dark:bg-gray-800/50">
          <button
            @click="emit('close')"
            class="px-4 py-2 text-xs font-bold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            取消
          </button>
          <button
            @click="emit('submit')"
            :disabled="saving"
            class="px-4 py-2 text-xs font-bold text-white bg-primary rounded-xl hover:bg-primary-hover active:bg-primary-active disabled:opacity-50 transition-colors flex items-center space-x-1.5"
          >
            <svg v-if="saving" class="w-3.5 h-3.5 animate-spin text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            <span>{{ editing ? '保存修改' : '沉淀报表' }}</span>
          </button>
        </div>
      </div>
    </div>
    </teleport>

</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(156, 163, 175, 0.3);
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(156, 163, 175, 0.5);
}
.custom-scrollbar-embed::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar-embed::-webkit-scrollbar-thumb {
  background-color: rgba(156, 163, 175, 0.5);
  border-radius: 2px;
}
</style>
