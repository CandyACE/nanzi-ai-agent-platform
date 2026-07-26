<script setup lang="ts">
interface MountedResource {
  key: string;
  icon: string;
  label: string;
  type: string;
  id?: string;
  scope?: string;
}

defineProps<{
  projectName: string;
  resourceCount: number;
  mountedResources: MountedResource[];
}>();

const emit = defineEmits<{
  (event: "manage"): void;
  (event: "remove", resource: MountedResource): void;
}>();
</script>

<template>
  <div class="flex-shrink-0 px-4 py-2 flex items-center gap-2 text-[11px] text-gray-500 dark:text-gray-400 overflow-x-auto border-b border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/20">
    <span class="font-bold shrink-0">{{ projectName ? `📁 ${projectName}` : '📌 会话固定资源' }}</span>
    <span v-if="resourceCount === 0" class="text-gray-400 shrink-0">未挂载，按默认权限自动使用</span>
    <template v-else>
      <span
        v-for="item in mountedResources"
        :key="item.key"
        class="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-100 shrink-0 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800"
        :title="`当前会话已锁定在【${item.label}】范围内，AI 问数时将仅分析此资源。点击 × 可解绑。`"
      >
        {{ item.icon }} {{ item.label }}
        <button
          type="button"
          class="hover:text-red-600 dark:hover:text-red-400"
          title="移除资源"
          @click="emit('remove', item)"
        >×</button>
      </span>
    </template>
    <button
      type="button"
      class="px-2 py-1 rounded-full border border-gray-200 hover:border-primary hover:text-primary dark:border-gray-700 dark:hover:border-primary shrink-0"
      @click="emit('manage')"
    >
      管理会话资源
    </button>
  </div>
</template>
