<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const emit = defineEmits<{
  (e: 'action', type: 'sync_all'): void
  (e: 'close'): void
  (e: 'dismiss'): void
}>()

const router = useRouter()
const isCollapsed = ref(true)

const steps = [
  {
    step: 1,
    title: '样本沉淀与录入',
    subtitle: '会话采纳点赞与专家录入',
    desc: '用户在 Chat 对话中对满意答案/SQL 点击「采纳点赞」，系统自动提取意图与 SQL 沉淀为待审样本；专家亦可后台手动录入。',
    tag: '数据来源',
    tagClass: 'bg-cyan-50 text-cyan-700 border-cyan-200',
    iconBg: 'bg-cyan-600 text-white font-bold',
    actionText: '前往对话',
    actionType: 'chat' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 2,
    title: '专家审核与打标',
    subtitle: '清洗意图与黄金 SQL 确认',
    desc: '管理员进入「待审核」列表，校验自然语言意图（Refined Query）与 SQL 标准性；通过审批后正式纳入经验案例库。',
    tag: '质量把关',
    tagClass: 'bg-blue-50 text-blue-700 border-blue-200',
    iconBg: 'bg-blue-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '待审核 Tab 下逐条审批',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 3,
    title: '向量同步与索引',
    subtitle: 'RAGFlow/Redis 向量化',
    desc: '审核通过的案例需同步至向量索引库；支持单个案例同步或顶部一键全量同步，构建语义密集检索向量。',
    tag: '索引构建',
    tagClass: 'bg-teal-50 text-teal-700 border-teal-200',
    iconBg: 'bg-teal-600 text-white font-bold',
    actionText: '一键全量同步',
    actionType: 'sync_all' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 4,
    title: '动态 Few-Shot 召回',
    subtitle: '问答上下文动态注入',
    desc: '智能体接收到用户新提问时，后台通过向量检索秒级召回最相似的 1~3 条案例注入 Prompt，辅助大模型生成高精度 SQL。',
    tag: '大模型消费',
    tagClass: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    iconBg: 'bg-indigo-600 text-white font-bold',
    actionText: '前往智能体中心',
    actionType: 'agents' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 5,
    title: '引用统计与持续迭代',
    subtitle: 'use_count 统计与飞轮进化',
    desc: '系统自动统计每条案例的真实引用频次（use_count），对过时或低质案例标记「废弃」，持续维持高水准业务经验库。',
    tag: '飞轮迭代',
    tagClass: 'bg-amber-50 text-amber-700 border-amber-200',
    iconBg: 'bg-amber-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '卡片查看引用次数与点赞',
    secondaryActionText: null,
    secondaryActionType: null
  }
]

const handleAction = (type: 'chat' | 'sync_all' | 'agents' | null) => {
  if (!type) return
  if (type === 'chat') {
    router.push('/dashboard/chat')
  } else if (type === 'agents') {
    router.push('/dashboard/agent-management')
  } else if (type === 'sync_all') {
    emit('action', 'sync_all')
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
    aria-label="案例集管理全流程指引"
    class="relative overflow-hidden rounded-2xl border border-cyan-100 bg-gradient-to-r from-cyan-50/70 via-blue-50/40 to-slate-50/60 p-4 shadow-sm transition-all sm:p-5"
  >
    <!-- 背景光晕装饰 -->
    <div
      class="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-cyan-200/30 blur-3xl"
      aria-hidden="true"
    ></div>
    <div
      class="pointer-events-none absolute left-1/3 -bottom-20 h-40 w-40 rounded-full bg-blue-200/25 blur-2xl"
      aria-hidden="true"
    ></div>

    <!-- 顶部标题与控制栏 -->
    <div class="relative z-10 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-cyan-600 text-white shadow-md shadow-cyan-600/30"
          style="background-color: #0891b2; color: #ffffff;"
        >
          <svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-bold text-gray-900 sm:text-base">
              案例集全生命周期沉淀与应用指引
            </h3>
            <span
              class="rounded-full bg-cyan-100/80 px-2 py-0.5 text-[11px] font-semibold text-cyan-700"
            >
              Few-Shot 学习闭环
            </span>
          </div>
          <p class="mt-0.5 text-xs text-gray-500">
            理解案例「从哪里来、如何审核向量化、如何在智能体问答中秒级 Few-Shot 召回注入提升准确率」
          </p>
        </div>
      </div>

      <!-- 右侧快捷控制按钮 -->
      <div class="flex items-center gap-1.5 sm:gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white/80 px-2.5 py-1 text-xs font-medium text-gray-600 shadow-2xs hover:bg-white hover:text-gray-900 transition-colors cursor-pointer"
          @click="isCollapsed = !isCollapsed"
        >
          <span>{{ isCollapsed ? '展开流程' : '收起' }}</span>
          <svg
            class="h-3.5 w-3.5 transition-transform duration-200"
            :class="{ 'rotate-180': !isCollapsed }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <button
          type="button"
          class="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white/80 px-2.5 py-1 text-xs font-medium text-gray-500 shadow-2xs hover:bg-white hover:text-amber-600 transition-colors cursor-pointer"
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

    <!-- 5 步骤流程卡片网格 -->
    <div
      v-show="!isCollapsed"
      class="relative z-10 mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5"
    >
      <div
        v-for="(item, idx) in steps"
        :key="item.step"
        class="group relative flex flex-col justify-between rounded-xl border border-white/80 bg-white/85 p-3.5 shadow-2xs backdrop-blur-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-white hover:shadow-md"
      >
        <!-- 连接箭头（仅在桌面端第 1~4 步显示） -->
        <div
          v-if="idx < steps.length - 1"
          class="pointer-events-none absolute -right-2 top-1/2 z-20 hidden -translate-y-1/2 text-cyan-300 lg:block"
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
            <p class="text-[11px] font-medium text-cyan-900/80">{{ item.subtitle }}</p>
            <p class="mt-1 text-xs leading-relaxed text-gray-500">{{ item.desc }}</p>
          </div>
        </div>

        <!-- 底部快捷动作 -->
        <div class="mt-3.5 border-t border-gray-100/80 pt-2.5">
          <div v-if="item.actionType" class="flex items-center gap-1.5">
            <button
              type="button"
              class="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-cyan-200 bg-cyan-50/60 py-1 text-xs font-medium text-cyan-700 hover:bg-cyan-600 hover:text-white transition-colors cursor-pointer"
              @click="handleAction(item.actionType)"
            >
              <span>{{ item.actionText }}</span>
              <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
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
