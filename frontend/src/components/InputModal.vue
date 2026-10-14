<script setup lang="ts">
/**
 * 通用文本输入弹窗。
 *
 * 项目的确认类弹窗（`ConfirmModal`）不承载输入，此前需要"让用户填一个名字"的地方
 * 就直接用了原生 `window.prompt`——原生弹窗会阻塞主线程、样式无法跟主题一致、在
 * 部分内嵌 WebView 里还会被浏览器直接拦截，与「禁止原生 alert 系列」的既有约定也不符。
 *
 * 遮罩同样走 `<Teleport to="body">`：祖先链上任何 `transform`（如页面切换动画的
 * `translateY`）都会改写 `fixed` 的包含块，导致遮罩只盖内容区、压不住顶栏与侧边栏。
 * 详见 `tests/frontend/test_guide_overlay_contract.py`。
 */
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

interface Props {
  title: string
  modelValue: string
  message?: string
  placeholder?: string
  hint?: string
  confirmText?: string
  cancelText?: string
  loading?: boolean
  maxlength?: number
}

const props = withDefaults(defineProps<Props>(), {
  message: '',
  placeholder: '',
  hint: '',
  confirmText: '确定',
  cancelText: '取消',
  loading: false,
  maxlength: 128,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'confirm', value: string): void
  (e: 'cancel'): void
}>()

const draft = ref(props.modelValue)
const inputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.modelValue,
  (value) => {
    draft.value = value
  }
)

const submit = () => {
  if (props.loading) return
  // 统一 trim：技能 ID / 名称这类值带前后空格几乎总是笔误，交给调用方再判空更省事
  emit('confirm', draft.value.trim())
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    if (!props.loading) emit('cancel')
  } else if (event.key === 'Enter') {
    event.preventDefault()
    event.stopPropagation()
    submit()
  }
}

onMounted(async () => {
  await nextTick()
  inputRef.value?.focus()
  inputRef.value?.select()
  document.addEventListener('keydown', handleKeydown, true)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown, true)
})
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-[13000] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      @click.self="!loading && $emit('cancel')"
    >
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full overflow-hidden">
        <form class="p-6" @submit.prevent="submit">
          <h3 class="text-lg leading-6 font-medium text-gray-900 dark:text-gray-100">
            {{ title }}
          </h3>
          <p v-if="message" class="mt-2 text-sm text-gray-500 dark:text-gray-400 whitespace-pre-line">
            {{ message }}
          </p>
          <input
            ref="inputRef"
            v-model="draft"
            type="text"
            :placeholder="placeholder"
            :maxlength="maxlength"
            class="mt-4 w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm text-gray-900 shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
          />
          <p v-if="hint" class="mt-2 text-xs text-gray-400 dark:text-gray-500">{{ hint }}</p>
        </form>
        <div class="flex flex-row-reverse gap-3 bg-gray-50 px-4 py-3 dark:bg-gray-900/50">
          <button
            type="button"
            :disabled="loading"
            class="inline-flex items-center justify-center gap-1.5 rounded-md border border-transparent bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm transition-all hover:bg-primary-dark focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            @click="submit"
          >
            <svg v-if="loading" class="h-4 w-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>{{ loading ? '处理中...' : confirmText }}</span>
          </button>
          <button
            type="button"
            :disabled="loading"
            class="inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
            @click="$emit('cancel')"
          >
            {{ cancelText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
