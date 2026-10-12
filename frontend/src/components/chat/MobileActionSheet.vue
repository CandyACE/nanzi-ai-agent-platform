<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[260] flex items-end bg-black/35 backdrop-blur-[1px]"
      @click.self="close"
    >
      <div
        ref="sheetRef"
        class="w-full rounded-t-2xl border-t border-gray-100 bg-white p-4 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-2xl dark:border-gray-800 dark:bg-gray-900"
        role="dialog"
        aria-modal="true"
        :aria-label="title || '操作面板'"
        tabindex="-1"
      >
        <div class="mx-auto mb-3 h-1 w-10 rounded-full bg-gray-300 dark:bg-gray-600" />
        <div v-if="title || subtitle" class="mb-2 flex items-center justify-between gap-3">
          <div class="min-w-0">
            <h3 v-if="title" class="text-sm font-bold text-gray-800 dark:text-gray-100">{{ title }}</h3>
            <p v-if="subtitle" class="mt-0.5 text-[11px] text-gray-400">{{ subtitle }}</p>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-full p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800"
            aria-label="关闭"
            @click="close"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div class="max-h-[70vh] overflow-y-auto">
          <slot />
        </div>
        <button
          type="button"
          class="mt-3 w-full rounded-xl py-2 text-center text-xs text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          @click="close"
        >
          {{ closeLabel }}
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, onUnmounted, ref, watch } from "vue";

/**
 * 移动端底部操作抽屉的壳。
 *
 * 只负责：Teleport 到 body、遮罩、贴底容器、安全区、点遮罩 / Esc / 取消关闭、
 * 打开期间锁背景滚动、可访问性属性。业务内容一律走默认插槽。
 *
 * 使用约束：请**常驻挂载**、用 :open 切换显隐（不要用 v-if 包住本组件）——
 * 壳靠 open 的变化来锁 / 放背景滚动，挂载时 open 已经是 true 的话不会触发 watch。
 */
const props = withDefaults(
  defineProps<{
    open: boolean;
    title?: string;
    subtitle?: string;
    closeLabel?: string;
  }>(),
  { title: "", subtitle: "", closeLabel: "取消" },
);
const emit = defineEmits<{ (event: "close"): void }>();

const sheetRef = ref<HTMLElement | null>(null);
let previousBodyOverflow: string | null = null;

const close = () => emit("close");

const lockBodyScroll = () => {
  // SSR / 单测环境没有 document
  if (typeof document === "undefined" || previousBodyOverflow !== null) return;
  previousBodyOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
};
const unlockBodyScroll = () => {
  if (typeof document === "undefined" || previousBodyOverflow === null) return;
  document.body.style.overflow = previousBodyOverflow;
  previousBodyOverflow = null;
};
const onKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape") close();
};

watch(
  () => props.open,
  async (open) => {
    if (open) {
      lockBodyScroll();
      document.addEventListener("keydown", onKeydown);
      await nextTick();
      sheetRef.value?.focus();
      return;
    }
    unlockBodyScroll();
    document.removeEventListener("keydown", onKeydown);
  },
);

onUnmounted(() => {
  unlockBodyScroll();
  if (typeof document !== "undefined") document.removeEventListener("keydown", onKeydown);
});
</script>
