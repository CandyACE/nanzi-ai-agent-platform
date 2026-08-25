<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const props = withDefaults(
  defineProps<{
    collapsible?: boolean
  }>(),
  {
    collapsible: true
  }
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'dismiss'): void
  (e: 'action', type: 'datasource' | 'import' | 'create'): void
}>()

const router = useRouter()
const isCollapsed = ref(true)

const steps = [
  {
    step: 1,
    title: '连接与摸排数据源',
    subtitle: '配置物理连接与表画像',
    desc: '配置 MySQL、PostgreSQL、ClickHouse 等外部库连接，支持连通性测试与一键智能摸排表结构画像。',
    tag: '基础准备',
    tagClass: 'bg-blue-50 text-blue-700 border-blue-200',
    iconBg: 'bg-blue-600 text-white font-bold',
    actionText: '去管理数据源',
    actionType: 'datasource' as const,
    hintText: ''
  },
  {
    step: 2,
    title: '智能导入与 AI 解析',
    subtitle: '自动提取业务语义与枚举',
    desc: '通过画像免推理导入、库表直读或 DDL 粘贴，AI 自动提取中文业务名、字段描述、字典枚举及主键。',
    tag: '语义生成',
    tagClass: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    iconBg: 'bg-indigo-600 text-white font-bold',
    actionText: '向导新建数据集',
    actionType: 'import' as const,
    hintText: ''
  },
  {
    step: 3,
    title: '建模指标与实体关系',
    subtitle: '定义计算口径与关联拓扑',
    desc: '在数据集中维护业务指标计算公式（Metrics），定义 1:1、1:N 实体关联与跨库 Join 图谱。',
    tag: '语义建模',
    tagClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    iconBg: 'bg-emerald-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '点击下方数据集进入配置'
  },
  {
    step: 4,
    title: '向量同步与智能体挂载',
    subtitle: '供 ChatBI 与 Agent 精准检索',
    desc: '一键将数据集导出为紧凑 YAML 并同步至向量库，供 ChatBI 与 Agent 智能体精准召回并生成 SQL。',
    tag: '消费应用',
    tagClass: 'bg-amber-50 text-amber-700 border-amber-200',
    iconBg: 'bg-amber-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '在智能体编排中生效'
  }
]

const handleAction = (type: 'datasource' | 'import' | 'create' | null) => {
  if (type === 'datasource') {
    router.push('/dashboard/data-sources')
  } else if (type === 'import' || type === 'create') {
    emit('action', type)
  }
}

const handleClose = () => {
  emit('close')
}

const handleDismiss = () => {
  emit('dismiss')
}
</script>

<template>
  <section
    aria-label="元数据管理流程指引"
    class="relative overflow-hidden rounded-2xl border border-blue-100/80 bg-gradient-to-br from-blue-50/90 via-indigo-50/40 to-white p-4 shadow-sm sm:p-5 transition-all duration-300"
  >
    <!-- 背景微装饰光晕 -->
    <div class="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-blue-400/10 blur-2xl" />
    <div class="pointer-events-none absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-indigo-400/10 blur-2xl" />

    <!-- 顶部标题与控制区域 -->
    <div class="relative z-10 flex flex-wrap items-center justify-between gap-3 border-b border-blue-100/60 pb-3">
      <div class="flex items-center gap-2.5">
        <div
          class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm shadow-blue-500/30"
          style="background-color: #2563eb; color: #ffffff;"
        >
          <svg class="h-4 w-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h2 class="text-base font-bold text-gray-900">元数据管理全流程指引</h2>
            <span class="inline-flex items-center rounded-full bg-blue-100/80 px-2 py-0.5 text-xs font-semibold text-blue-700">
              4 步构建语义大脑
            </span>
          </div>
          <p class="text-xs text-gray-500">
            物理数据库到 AI 语义模型的生命周期管理，助力 Text-to-SQL 准确率提升
          </p>
        </div>
      </div>

      <!-- 右侧操作栏 -->
      <div class="flex items-center gap-2">
        <button
          v-if="collapsible"
          type="button"
          class="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-blue-100/60 hover:text-gray-900 transition-colors cursor-pointer"
          @click="isCollapsed = !isCollapsed"
        >
          <span>{{ isCollapsed ? '展开流程' : '收起' }}</span>
          <svg
            class="h-3.5 w-3.5 transition-transform duration-200"
            :class="{ 'rotate-180': isCollapsed }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <button
          type="button"
          class="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white/80 px-2.5 py-1 text-xs font-medium text-gray-600 hover:border-gray-300 hover:bg-white hover:text-gray-900 transition-colors shadow-2xs cursor-pointer"
          title="下次进入不再主动弹出此引导"
          @click="handleDismiss"
        >
          <svg class="h-3.5 w-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
          </svg>
          <span>不再提示</span>
        </button>

        <button
          type="button"
          class="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-200/50 hover:text-gray-700 transition-colors cursor-pointer"
          title="关闭本次指引"
          @click="handleClose"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>

    <!-- 4 步骤流程卡片网格 -->
    <div
      v-show="!isCollapsed"
      class="relative z-10 mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
    >
      <div
        v-for="(item, idx) in steps"
        :key="item.step"
        class="group relative flex flex-col justify-between rounded-xl border border-white/80 bg-white/75 p-3.5 shadow-2xs backdrop-blur-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-200 hover:bg-white hover:shadow-md"
      >
        <!-- 连接箭头（仅在桌面端第 1~3 步显示） -->
        <div
          v-if="idx < steps.length - 1"
          class="pointer-events-none absolute -right-2 top-1/2 z-20 hidden -translate-y-1/2 text-blue-300 lg:block"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7" />
          </svg>
        </div>

        <div>
          <!-- 卡片头部：序号与标签 -->
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <span
                class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold shadow-xs"
                :class="item.iconBg"
              >
                {{ item.step }}
              </span>
              <span class="text-xs font-semibold text-gray-900">{{ item.title }}</span>
            </div>
            <span
              class="rounded-md border px-1.5 py-0.5 text-[10px] font-medium"
              :class="item.tagClass"
            >
              {{ item.tag }}
            </span>
          </div>

          <!-- 副标题与说明文案 -->
          <div class="mt-2.5">
            <p class="text-[11px] font-medium text-blue-900/80">{{ item.subtitle }}</p>
            <p class="mt-1 text-xs leading-relaxed text-gray-500">{{ item.desc }}</p>
          </div>
        </div>

        <!-- 底部快捷动作 -->
        <div class="mt-3.5 border-t border-gray-100/80 pt-2.5">
          <button
            v-if="item.actionType"
            type="button"
            class="inline-flex w-full items-center justify-center gap-1 rounded-lg border border-blue-200 bg-blue-50/50 py-1 text-xs font-medium text-blue-700 hover:bg-blue-600 hover:text-white transition-colors cursor-pointer"
            @click="handleAction(item.actionType)"
          >
            <span>{{ item.actionText }}</span>
            <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </button>
          <div
            v-else
            class="flex items-center justify-center rounded-lg bg-gray-50/80 py-1 text-[11px] font-medium text-gray-400"
          >
            <span>{{ item.hintText }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
