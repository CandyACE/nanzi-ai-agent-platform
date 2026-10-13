<script setup lang="ts">
/**
 * 可搜索的模型下拉：用于版本配置（编排/合成模型）、工具高级配置与系统配置（默认/多模态模型）。
 *
 * 原生 <select> 无法搜索，模型多起来（几十条）只能一条条找；
 * 这里用「触发器 + Teleport 到 body 的浮层」实现，避免被抽屉/弹窗的 overflow 容器裁掉。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  buildModelOptions,
  buildPinnedModelOptions,
  filterSelectableModels,
  resolveModelSelectionLabel,
  shouldShowModelSearch,
  type ModelSelectOption,
  type SelectableModel,
} from '../../utils/modelSelect';

const props = withDefaults(defineProps<{
  modelValue: string;
  models: SelectableModel[];
  disabled?: boolean;
  /** 未选择任何模型时的占位文案 */
  placeholder?: string;
  /** 是否提供「跟随上层默认」的空选项（合成模型 / 工具覆盖模型需要） */
  allowEmpty?: boolean;
  emptyLabel?: string;
  searchPlaceholder?: string;
  /** 选项附带 model_id，便于区分同名模型 */
  showModelId?: boolean;
  /** 多模态模型的补充标签，例如「· 多模态」 */
  multimodalBadge?: string;
  /** 当前值不在候选列表中时（如来自环境变量的模型）给它的说明，例如「未知/环境变量」 */
  unknownOptionLabel?: string;
  /** 聚焦环配色，与所在卡片的主色保持一致 */
  accent?: 'primary' | 'emerald';
  /** 禁用态下补充说明，避免用户以为控件坏了 */
  disabledHint?: string;
}>(), {
  disabled: false,
  placeholder: '选择模型...',
  allowEmpty: false,
  emptyLabel: '跟随智能体默认配置',
  searchPlaceholder: '搜索模型名称或 ID…',
  showModelId: false,
  multimodalBadge: '',
  unknownOptionLabel: '',
  accent: 'primary',
  disabledHint: '',
});

const emit = defineEmits<{ 'update:modelValue': [value: string] }>();

const open = ref(false);
const query = ref('');
const activeIndex = ref(0);
const triggerRef = ref<HTMLButtonElement | null>(null);
const menuRef = ref<HTMLElement | null>(null);
const searchRef = ref<HTMLInputElement | null>(null);
const listRef = ref<HTMLElement | null>(null);
const menuStyle = ref<Record<string, string>>({});

type Option = ModelSelectOption;

const showSearch = computed(() => shouldShowModelSearch((props.models || []).length));
const isPlaceholder = computed(() => !props.modelValue);
const currentLabel = computed(() => resolveModelSelectionLabel(props.models, props.modelValue, {
  allowEmpty: props.allowEmpty,
  emptyLabel: props.emptyLabel,
  placeholder: props.placeholder,
  showModelId: props.showModelId,
  unknownOptionLabel: props.unknownOptionLabel,
}));
const filteredModels = computed(() => filterSelectableModels(props.models, query.value));
const optionLabelOptions = computed(() => ({
  showModelId: props.showModelId,
  multimodalBadge: props.multimodalBadge,
}));
const options = computed<Option[]>(() => [
  // 置顶项（列表外的当前值 / 空选项）不参与搜索过滤，否则用户会以为当前配置丢了
  ...buildPinnedModelOptions(props.models, props.modelValue, {
    allowEmpty: props.allowEmpty,
    emptyLabel: props.emptyLabel,
    unknownOptionLabel: props.unknownOptionLabel,
  }),
  ...buildModelOptions(filteredModels.value, optionLabelOptions.value),
]);
const hasNoMatch = computed(() => filteredModels.value.length === 0);
const triggerFocusClass = computed(() =>
  props.accent === 'emerald' ? 'focus:ring-2 focus:ring-emerald-500/30' : 'focus:ring-2 focus:ring-primary/30',
);

const updateMenuPosition = () => {
  const el = triggerRef.value;
  if (!el || typeof window === 'undefined') return;
  const rect = el.getBoundingClientRect();
  const estimatedMenuHeight = 288;
  const spaceBelow = window.innerHeight - rect.bottom;
  // 下方空间不足且上方更宽敞时向上弹，避免浮层贴到视口外
  const openUpward = spaceBelow < Math.min(estimatedMenuHeight, 224) && rect.top > spaceBelow;
  menuStyle.value = {
    position: 'fixed',
    left: `${Math.max(8, rect.left)}px`,
    width: `${rect.width}px`,
    zIndex: '10100',
    ...(openUpward
      ? { top: 'auto', bottom: `${Math.max(8, window.innerHeight - rect.top + 4)}px` }
      : { top: `${rect.bottom + 4}px`, bottom: 'auto' }),
  };
};

const scrollActiveIntoView = () => {
  void nextTick(() => {
    const item = listRef.value?.querySelector<HTMLElement>(`[data-option-index="${activeIndex.value}"]`);
    item?.scrollIntoView({ block: 'nearest' });
  });
};

const closeMenu = () => {
  open.value = false;
  query.value = '';
};

const openMenu = async () => {
  if (props.disabled) return;
  query.value = '';
  open.value = true;
  const currentIndex = options.value.findIndex((option) => option.value === props.modelValue);
  activeIndex.value = currentIndex >= 0 ? currentIndex : 0;
  updateMenuPosition();
  await nextTick();
  if (showSearch.value) searchRef.value?.focus();
  scrollActiveIntoView();
};

const toggleMenu = () => {
  if (open.value) closeMenu();
  else void openMenu();
};

const selectOption = (value: string) => {
  if (value !== props.modelValue) emit('update:modelValue', value);
  closeMenu();
  triggerRef.value?.focus();
};

const moveActive = (delta: number) => {
  const total = options.value.length;
  if (!total) return;
  activeIndex.value = (activeIndex.value + delta + total) % total;
  scrollActiveIntoView();
};

const confirmActive = () => {
  const option = options.value[activeIndex.value];
  if (option) selectOption(option.value);
};

const onTriggerKeydown = (event: KeyboardEvent) => {
  if (props.disabled) return;
  if (!open.value) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      void openMenu();
    }
    return;
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    moveActive(1);
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    moveActive(-1);
  } else if (event.key === 'Enter') {
    event.preventDefault();
    confirmActive();
  } else if (event.key === 'Escape') {
    event.preventDefault();
    closeMenu();
  }
};

const onSearchKeydown = (event: KeyboardEvent) => {
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    moveActive(1);
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    moveActive(-1);
  } else if (event.key === 'Enter') {
    event.preventDefault();
    confirmActive();
  } else if (event.key === 'Escape') {
    event.preventDefault();
    closeMenu();
    triggerRef.value?.focus();
  }
};

const onDocumentPointerDown = (event: MouseEvent) => {
  if (!open.value) return;
  const target = event.target as Node | null;
  if (target && (triggerRef.value?.contains(target) || menuRef.value?.contains(target))) return;
  closeMenu();
};

const onViewportChange = (event?: Event) => {
  if (!open.value) return;
  const target = (event?.target || null) as Node | null;
  // 浮层内部滚动不需要重新定位，否则列表滚动会抖
  if (target && menuRef.value?.contains(target)) return;
  updateMenuPosition();
};

watch(() => props.modelValue, () => {
  if (open.value) closeMenu();
});
watch(() => props.disabled, (value) => {
  if (value && open.value) closeMenu();
});

onMounted(() => {
  document.addEventListener('mousedown', onDocumentPointerDown);
  window.addEventListener('resize', onViewportChange);
  window.addEventListener('scroll', onViewportChange, true);
});

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentPointerDown);
  window.removeEventListener('resize', onViewportChange);
  window.removeEventListener('scroll', onViewportChange, true);
});
</script>

<template>
  <div class="relative">
    <button
      ref="triggerRef"
      type="button"
      role="combobox"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :disabled="disabled"
      :title="disabled && disabledHint ? disabledHint : undefined"
      class="flex w-full items-center justify-between gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-sm outline-none transition-colors"
      :class="[
        triggerFocusClass,
        disabled ? 'cursor-not-allowed bg-gray-50 text-gray-400' : 'hover:border-gray-300',
        open ? 'border-gray-300' : '',
      ]"
      @click="toggleMenu"
      @keydown="onTriggerKeydown"
    >
      <span class="truncate" :class="isPlaceholder ? 'text-gray-400' : 'text-gray-900'">{{ currentLabel }}</span>
      <svg
        class="h-4 w-4 flex-shrink-0 text-gray-400 transition-transform duration-200"
        :class="{ 'rotate-180': open }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        ref="menuRef"
        :style="menuStyle"
        class="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-2xl"
      >
        <div v-if="showSearch" class="border-b border-gray-100 p-2">
          <input
            ref="searchRef"
            v-model="query"
            type="text"
            :placeholder="searchPlaceholder"
            class="w-full rounded-lg border border-gray-200 px-2.5 py-1.5 text-xs text-gray-700 outline-none focus:ring-2 focus:ring-primary/20"
            @keydown="onSearchKeydown"
          />
        </div>
        <div ref="listRef" role="listbox" class="max-h-64 overflow-y-auto p-1.5">
          <button
            v-for="(option, index) in options"
            :key="option.value || '__empty_option__'"
            type="button"
            role="option"
            :aria-selected="option.value === modelValue"
            :data-option-index="index"
            class="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors"
            :class="[
              index === activeIndex ? 'bg-primary/10 text-primary' : 'text-gray-700 hover:bg-gray-50',
              option.value === modelValue ? 'font-semibold' : '',
            ]"
            @mouseenter="activeIndex = index"
            @click="selectOption(option.value)"
          >
            <span class="truncate">{{ option.label }}</span>
            <svg
              v-if="option.value === modelValue"
              class="h-3.5 w-3.5 flex-shrink-0 text-primary"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
            </svg>
          </button>
          <div v-if="hasNoMatch" class="px-2.5 py-6 text-center text-xs text-gray-400">
            {{ query.trim() ? '无匹配模型' : '暂无可选模型' }}
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
