<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { UserQuestionState } from "@/utils/userQuestion";

const props = defineProps<{
  payload: UserQuestionState;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (event: "submit", payload: { selectedOptionIds: string[]; customInput: string; cancelled: boolean }): void;
}>();

const selectedOptionIds = ref<string[]>([]);
const customInput = ref("");

watch(
  () => props.payload.question_id,
  () => {
    selectedOptionIds.value = [...(props.payload.selected_option_ids || [])];
    customInput.value = props.payload.custom_input || "";
  },
  { immediate: true },
);

const locked = computed(
  () =>
    Boolean(props.disabled) ||
    props.payload.status === "submitted" ||
    props.payload.status === "cancelled" ||
    props.payload.status === "stale",
);

const statusLabel = computed(() => {
  if (props.payload.status === "submitted") return "已提交";
  if (props.payload.status === "cancelled") return "已取消";
  if (props.payload.status === "stale") return "已失效";
  return "等待回答";
});

function toggleOption(id: string) {
  if (locked.value) return;
  if (props.payload.is_multi_select) {
    selectedOptionIds.value = selectedOptionIds.value.includes(id)
      ? selectedOptionIds.value.filter((item) => item !== id)
      : [...selectedOptionIds.value, id];
    return;
  }
  selectedOptionIds.value = [id];
}

function submit() {
  if (locked.value) return;
  emit("submit", {
    selectedOptionIds: [...selectedOptionIds.value],
    customInput: customInput.value.trim(),
    cancelled: false,
  });
}

function cancel() {
  if (locked.value) return;
  emit("submit", {
    selectedOptionIds: [],
    customInput: "",
    cancelled: true,
  });
}
</script>

<template>
  <!-- UserQuestionCard is an AI-initiated question, not a business confirmation. -->
  <section
    class="mt-3 rounded-lg border border-violet-200 bg-violet-50/80 p-3 text-xs text-violet-950 shadow-sm dark:border-violet-900/50 dark:bg-violet-900/20 dark:text-violet-100"
    role="group"
    :aria-label="payload.question || 'AI 提问'"
  >
    <div class="flex items-start gap-2">
      <div class="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.25 9.75h7.5m-7.5 3h4.5m-8.25 7.5 2.16-4.32A8.25 8.25 0 1 1 12 20.25c-1.8 0-3.46-.58-4.8-1.57Z" />
        </svg>
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex items-center justify-between gap-3">
          <div class="font-bold text-violet-900 dark:text-violet-100">需要你的补充</div>
          <span
            class="rounded-full px-2 py-0.5 text-[10px] font-bold"
            :class="{
              'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300': payload.status === 'pending',
              'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300': payload.status === 'submitted',
              'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300': payload.status === 'cancelled',
              'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300': payload.status === 'stale',
            }"
          >{{ statusLabel }}</span>
        </div>
        <p class="mt-1 break-words text-sm font-medium text-violet-900 dark:text-violet-100">{{ payload.question }}</p>
        <p v-if="payload.context" class="mt-1 break-words text-violet-800/75 dark:text-violet-200/75">{{ payload.context }}</p>

        <div class="mt-3 space-y-2">
          <button
            v-for="option in payload.options"
            :key="option.id"
            type="button"
            class="flex w-full items-start gap-2 rounded-md border bg-white/80 px-3 py-2 text-left transition-colors dark:bg-gray-950/30"
            :class="selectedOptionIds.includes(option.id) ? 'border-violet-500 ring-1 ring-violet-300 dark:border-violet-400' : 'border-violet-100 hover:border-violet-300 dark:border-violet-900/40 dark:hover:border-violet-700'"
            :disabled="locked"
            @click="toggleOption(option.id)"
          >
            <span class="mt-0.5 flex h-3.5 w-3.5 flex-shrink-0 items-center justify-center rounded-full border border-violet-400" :class="selectedOptionIds.includes(option.id) ? 'bg-violet-600' : 'bg-transparent'">
              <span v-if="selectedOptionIds.includes(option.id)" class="h-1.5 w-1.5 rounded-full bg-white" />
            </span>
            <span class="min-w-0">
              <span class="block font-semibold">{{ option.label }}</span>
              <span v-if="option.description" class="mt-0.5 block text-[11px] text-violet-800/70 dark:text-violet-200/70">{{ option.description }}</span>
            </span>
          </button>
        </div>

        <textarea
          v-if="payload.allow_custom_input"
          v-model="customInput"
          rows="2"
          class="mt-3 w-full rounded-md border border-violet-100 bg-white px-2 py-1.5 text-xs text-gray-800 outline-none focus:border-violet-400 disabled:cursor-not-allowed disabled:bg-gray-50 dark:border-violet-900/50 dark:bg-gray-900 dark:text-gray-100"
          :disabled="locked"
          placeholder="也可以补充说明（可选）"
        />

        <button
          v-if="payload.status === 'pending'"
          type="button"
          class="mt-3 inline-flex items-center rounded-md bg-violet-600 px-3 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="locked || (!selectedOptionIds.length && !customInput.trim())"
          @click="submit"
        >
          提交回答并继续
        </button>
        <button
          v-if="payload.status === 'pending'"
          type="button"
          class="ml-2 mt-3 inline-flex items-center rounded-md border border-violet-200 px-3 py-1.5 text-xs font-bold text-violet-700 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-violet-800 dark:text-violet-200 dark:hover:bg-violet-900/40"
          :disabled="locked"
          @click="cancel"
        >
          取消提问
        </button>
      </div>
    </div>
  </section>
</template>
