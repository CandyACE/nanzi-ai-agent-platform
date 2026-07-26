<script setup lang="ts">
import { nextTick, ref, watch } from "vue";

type ResourceScopeGroup = {
  key: string;
  label: string;
  shortLabel?: string;
  hint: string;
};

type ResourceScopeChip = {
  key: string;
  label: string;
  orphan?: boolean;
  item: any;
};

const props = defineProps<{
  visible: boolean;
  draft: Record<string, any>;
  groups: ResourceScopeGroup[];
  activeTab: string;
  orphanCount: number;
  loading: boolean;
  saving: boolean;
  optionSearch: Record<string, string>;
  selectedCount: (key: string) => number;
  orphanSelections: (key: string) => any[];
  selectedChips: (key: string) => ResourceScopeChip[];
  sortedOptions: (key: string) => any[];
  optionSelected: (key: string, option: any) => boolean;
  optionInitial: (option: any) => string;
  optionAccent: (index: number) => string;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "refresh"): void;
  (event: "save"): void;
  (event: "update:activeTab", value: string): void;
  (event: "remove-draft", type: string, item: any): void;
  (event: "toggle-option", type: string, option: any): void;
}>();

const projectNameInput = ref<HTMLInputElement | null>(null);

watch(() => props.visible, async (visible) => {
  if (!visible) return;
  await nextTick();
  projectNameInput.value?.focus();
});
</script>

<template>
  <div
    v-if="visible"
    class="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4"
    @click.self="emit('close')"
    @keydown.esc="emit('close')"
  >
    <div
      class="w-full max-w-2xl max-h-[88vh] flex flex-col overflow-hidden rounded-2xl bg-white dark:bg-gray-800 shadow-2xl"
      role="dialog"
      aria-labelledby="resource-scope-modal-title"
      aria-modal="true"
    >
      <div class="flex-shrink-0 px-5 pt-5 pb-3 border-b border-gray-100 dark:border-gray-700">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h3 id="resource-scope-modal-title" class="text-base font-black text-gray-900 dark:text-gray-100">项目会话资源</h3>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-relaxed">为本会话命名并可选定数据集、知识库与技能。保存后在本会话内持续生效。</p>
          </div>
          <button type="button" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none p-1" aria-label="关闭" @click="emit('close')">×</button>
        </div>
        <p class="mt-3 text-[11px] leading-relaxed rounded-lg bg-slate-50 dark:bg-gray-900/50 text-slate-600 dark:text-slate-400 border border-slate-100 dark:border-gray-700 px-3 py-2">
          不选择任何资源时，按账号默认权限使用；选择后仅允许已挂载项（数据集影响 ChatBI / 数据门户，知识库影响检索范围，技能影响自动匹配）。
        </p>
        <p v-if="orphanCount > 0" class="mt-2 text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-800/50 rounded-lg px-3 py-2">
          有 {{ orphanCount }} 项已保存的资源当前不可用，请移除或重新选择。
        </p>
      </div>

      <div class="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0">
        <label class="block">
          <span class="text-xs font-bold text-gray-500 dark:text-gray-400">项目名称 <span class="text-red-500">*</span></span>
          <input
            ref="projectNameInput"
            v-model="draft.project_name"
            class="mt-1.5 w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50/50 dark:bg-gray-900/30 px-3 py-2.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            placeholder="例如：销售经营分析"
          />
        </label>

        <div class="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col min-h-[280px]">
          <div class="flex border-b border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/40" role="tablist" aria-label="资源类型">
            <button
              v-for="group in groups"
              :key="group.key"
              type="button"
              role="tab"
              :id="`resource-scope-tab-${group.key}`"
              :aria-selected="activeTab === group.key"
              :aria-controls="`resource-scope-panel-${group.key}`"
              class="relative flex-1 min-w-0 px-2 py-2.5 text-xs font-bold transition-colors border-b-2 -mb-px"
              :class="activeTab === group.key
                ? 'border-primary text-primary bg-white dark:bg-gray-800'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'"
              @click="emit('update:activeTab', group.key)"
            >
              <span class="block truncate text-center">{{ group.shortLabel || group.label }}</span>
              <span class="mt-0.5 flex items-center justify-center gap-1">
                <span
                  v-if="selectedCount(group.key)"
                  class="text-[9px] font-black px-1 py-px rounded"
                  :class="activeTab === group.key ? 'bg-primary/15 text-primary' : 'bg-gray-200/80 dark:bg-gray-700 text-gray-600 dark:text-gray-300'"
                >{{ selectedCount(group.key) }}</span>
                <span v-if="orphanSelections(group.key).length" class="text-[9px] font-bold text-amber-600 dark:text-amber-400" title="有失效项">!</span>
              </span>
            </button>
          </div>

          <div
            v-for="group in groups"
            :key="'panel-' + group.key"
            v-show="activeTab === group.key"
            :id="`resource-scope-panel-${group.key}`"
            role="tabpanel"
            :aria-labelledby="`resource-scope-tab-${group.key}`"
            class="flex-1 p-3 space-y-2.5 min-h-0 flex flex-col"
          >
            <p class="text-[11px] text-gray-400 dark:text-gray-500 leading-relaxed shrink-0">{{ group.hint }}</p>

            <div v-if="selectedCount(group.key) > 0" class="flex flex-wrap gap-1.5 shrink-0">
              <button
                v-for="chip in selectedChips(group.key)"
                :key="chip.key"
                type="button"
                class="inline-flex items-center gap-1 max-w-full px-2 py-1 rounded-full text-[10px] font-bold border transition-colors"
                :class="chip.orphan
                  ? 'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700'
                  : 'bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800'"
                :title="chip.orphan ? '资源已不可用，点击移除' : '点击移除'"
                @click="emit('remove-draft', group.key, chip.item)"
              >
                <span class="truncate">{{ chip.label }}</span>
                <span class="shrink-0 opacity-70">×</span>
              </button>
            </div>

            <input
              v-model="optionSearch[group.key]"
              type="search"
              class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-transparent px-3 py-2 text-xs shrink-0"
              :placeholder="`搜索${group.label}`"
            />

            <div v-if="loading" class="text-xs text-gray-400 py-6 text-center flex-1">正在加载资源…</div>
            <div v-else-if="sortedOptions(group.key).length" class="space-y-0.5 flex-1 min-h-0 overflow-y-auto pr-0.5">
              <button
                v-for="(option, optionIndex) in sortedOptions(group.key)"
                :key="option.id"
                type="button"
                role="checkbox"
                :aria-checked="optionSelected(group.key, option)"
                class="w-full flex items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-colors border border-transparent"
                :class="optionSelected(group.key, option)
                  ? 'bg-primary/5 dark:bg-primary/10 border-primary/20'
                  : 'hover:bg-gray-50 dark:hover:bg-gray-700/60'"
                @click="emit('toggle-option', group.key, option)"
              >
                <span class="w-9 h-9 rounded-full flex items-center justify-center text-sm font-black text-white shrink-0" :class="optionAccent(optionIndex)">{{ optionInitial(option) }}</span>
                <span class="min-w-0 flex-1">
                  <span class="block text-sm font-bold text-gray-900 dark:text-gray-100 truncate" :title="option.name || option.id">{{ option.name || option.id }}</span>
                  <span class="block text-xs text-gray-400 dark:text-gray-500 truncate">{{ option.description || option.id }}</span>
                </span>
                <span
                  class="w-5 h-5 rounded-md border flex items-center justify-center shrink-0"
                  :class="optionSelected(group.key, option) ? 'bg-primary border-primary text-white' : 'border-gray-300 dark:border-gray-600'"
                >
                  <svg v-if="optionSelected(group.key, option)" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m5 12 4 4L19 6" /></svg>
                </span>
              </button>
            </div>
            <div v-else class="text-xs text-gray-400 py-6 text-center flex-1">
              {{ (optionSearch[group.key] || '').trim() ? '无匹配结果，试试清空搜索' : '暂无可选资源' }}
            </div>
          </div>
        </div>
      </div>

      <div class="flex-shrink-0 px-5 py-4 border-t border-gray-100 dark:border-gray-700 flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          class="px-2.5 py-1.5 rounded-lg text-xs text-gray-500 hover:text-primary hover:bg-blue-50 dark:hover:bg-gray-700 disabled:opacity-40"
          :disabled="loading || saving"
          @click="emit('refresh')"
        >
          ↻ 刷新资源列表
        </button>
        <div class="flex items-center gap-2 ml-auto">
          <button type="button" class="px-3 py-2 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" :disabled="saving" @click="emit('close')">取消</button>
          <button
            type="button"
            class="px-4 py-2 rounded-lg bg-primary text-white text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed min-w-[6.5rem]"
            :disabled="saving || !draft.project_name.trim()"
            @click="emit('save')"
          >
            {{ saving ? '保存中…' : '保存范围' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
