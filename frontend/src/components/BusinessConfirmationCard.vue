<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import type {
  BusinessConfirmationField,
  BusinessConfirmationState,
} from '@/utils/businessConfirmation';

const props = defineProps<{
  payload: BusinessConfirmationState;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (
    event: 'submit',
    payload: { confirmed: boolean; fields: BusinessConfirmationField[] },
  ): void;
}>();

const draftFields = reactive<BusinessConfirmationField[]>([]);

function syncDraft(fields: BusinessConfirmationField[]) {
  draftFields.splice(
    0,
    draftFields.length,
    ...fields.map((field) => ({
      key: field.key,
      label: field.label,
      value: field.value ?? '',
      editable: field.editable !== false,
      value_type: field.value_type || 'string',
    })),
  );
}

watch(
  () => props.payload,
  (next) => {
    syncDraft(next?.fields || []);
  },
  { immediate: true, deep: true },
);

const locked = computed(
  () =>
    props.disabled ||
    props.payload.status === 'submitted' ||
    props.payload.status === 'stale',
);

const statusLabel = computed(() => {
  if (props.payload.status === 'submitted') {
    return props.payload.decision === 'cancelled' ? '已取消' : '已确定';
  }
  if (props.payload.status === 'stale') return '已失效';
  return '待确认';
});

function onBooleanChange(field: BusinessConfirmationField, checked: boolean) {
  field.value = checked;
}

function submit(confirmed: boolean) {
  if (locked.value) return;
  emit('submit', {
    confirmed,
    fields: draftFields.map((field) => ({ ...field })),
  });
}
</script>

<template>
  <section
    class="mt-3 rounded-lg border border-sky-200 bg-sky-50/80 p-3 text-xs text-sky-950 shadow-sm dark:border-sky-900/50 dark:bg-sky-900/20 dark:text-sky-100"
    role="group"
    :aria-label="payload.title || '业务数据确认'"
  >
    <div class="flex items-start gap-2">
      <div
        class="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300"
      >
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex items-center justify-between gap-3">
          <div class="truncate font-bold text-sky-900 dark:text-sky-100">
            {{ payload.title || '请确认以下信息' }}
          </div>
          <span
            class="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
            :class="{
              'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300': payload.status === 'pending',
              'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300': payload.status === 'submitted' && payload.decision !== 'cancelled',
              'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300': payload.status === 'submitted' && payload.decision === 'cancelled',
              'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300': payload.status === 'stale',
            }"
          >
            {{ statusLabel }}
          </span>
        </div>

        <p
          v-if="payload.summary"
          class="mt-1 break-words text-sky-800/80 dark:text-sky-200/80"
        >
          {{ payload.summary }}
        </p>

        <div class="mt-3 overflow-hidden rounded-md border border-sky-100 bg-white/80 dark:border-sky-900/40 dark:bg-gray-950/30">
          <table class="w-full text-left">
            <thead class="bg-sky-50/80 text-[10px] uppercase tracking-wide text-sky-700 dark:bg-sky-950/40 dark:text-sky-300">
              <tr>
                <th class="px-2 py-1.5 font-semibold">字段名</th>
                <th class="px-2 py-1.5 font-semibold">字段值</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="field in draftFields"
                :key="field.key || field.label"
                class="border-t border-sky-100 dark:border-sky-900/40"
              >
                <td class="w-[36%] px-2 py-1.5 align-top font-medium text-sky-900 dark:text-sky-100">
                  {{ field.label }}
                </td>
                <td class="px-2 py-1.5 align-top">
                  <input
                    v-if="field.value_type === 'boolean'"
                    type="checkbox"
                    class="mt-0.5 h-3.5 w-3.5 rounded border-sky-300 text-sky-600 focus:ring-sky-500"
                    :checked="Boolean(field.value)"
                    :disabled="locked || field.editable === false"
                    @change="onBooleanChange(field, ($event.target as HTMLInputElement).checked)"
                  />
                  <textarea
                    v-else-if="field.value_type === 'text'"
                    v-model="field.value as string"
                    rows="2"
                    class="w-full rounded border border-sky-100 bg-white px-2 py-1 text-xs text-gray-800 outline-none focus:border-sky-400 disabled:cursor-not-allowed disabled:bg-gray-50 dark:border-sky-900/50 dark:bg-gray-900 dark:text-gray-100 dark:disabled:bg-gray-900/60"
                    :disabled="locked || field.editable === false"
                  />
                  <input
                    v-else
                    v-model="field.value as string | number"
                    :type="field.value_type === 'number' ? 'number' : 'text'"
                    class="w-full rounded border border-sky-100 bg-white px-2 py-1 text-xs text-gray-800 outline-none focus:border-sky-400 disabled:cursor-not-allowed disabled:bg-gray-50 dark:border-sky-900/50 dark:bg-gray-900 dark:text-gray-100 dark:disabled:bg-gray-900/60"
                    :disabled="locked || field.editable === false"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p
          v-if="payload.risk_note"
          class="mt-2 text-[11px] leading-5 text-sky-700/80 dark:text-sky-300/80"
        >
          风险提示：{{ payload.risk_note }}
        </p>

        <div v-if="payload.status === 'pending'" class="mt-3 flex items-center gap-2">
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-md bg-sky-600 px-3 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="locked"
            @click="submit(true)"
          >
            {{ payload.confirm_label || '确定' }}
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-bold text-gray-700 shadow-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
            :disabled="locked"
            @click="submit(false)"
          >
            {{ payload.cancel_label || '取消' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
