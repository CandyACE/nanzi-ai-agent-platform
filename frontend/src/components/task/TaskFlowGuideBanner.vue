<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const emit = defineEmits<{
  (e: 'action', type: 'create' | 'history'): void
  (e: 'close'): void
  (e: 'dismiss'): void
}>()

const router = useRouter()
const isCollapsed = ref(true)

const steps = [
  {
    step: 1,
    title: '任务创建与周期编排',
    subtitle: 'Cron 定时与智能体绑定',
    desc: '设定任务名称并绑定负责执行的目标智能体；设置每日/每周/每月定时周期与提示词，支持 AI 智能优化 Prompt。',
    tag: '触发编排',
    tagClass: 'bg-orange-50 text-orange-700 border-orange-200',
    iconBg: 'bg-orange-600 text-white font-bold',
    actionText: '新建任务',
    actionType: 'create' as const,
    hintText: '',
    secondaryActionText: '智能体中心',
    secondaryActionType: 'agents' as const
  },
  {
    step: 2,
    title: '资源限定与安全审批',
    subtitle: 'Scope 沙箱与审批策略',
    desc: '限定任务仅可调用的数据集、知识库、Skills 与 MCP 工具；设置 Allow 放行、Ask 人工授权或 Deny 拦截高危操作。',
    tag: '安全沙箱',
    tagClass: 'bg-blue-50 text-blue-700 border-blue-200',
    iconBg: 'bg-blue-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '编辑中设置资源与审批模式',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 3,
    title: '渠道分发与触达订阅',
    subtitle: '站内信/钉钉/企微/邮件',
    desc: '配置结果分发渠道，任务执行完毕后自动生成 Markdown 结构化报表并推送至群机器人、邮箱或沉淀至报告中心。',
    tag: '消息触达',
    tagClass: 'bg-teal-50 text-teal-700 border-teal-200',
    iconBg: 'bg-teal-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '通知配置中勾选推送渠道',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 4,
    title: '手动试跑与时序观测',
    subtitle: '立即执行与 Trace 观测',
    desc: '卡片上点击「立即执行」快速试跑验证；通过 Session Trace 时序链路全景观测大模型思考耗时与工具调用明细。',
    tag: '沙箱验证',
    tagClass: 'bg-purple-50 text-purple-700 border-purple-200',
    iconBg: 'bg-purple-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '卡片点击「立即执行」或 Trace',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 5,
    title: '健康监控与异常处置',
    subtitle: '执行记录与审计告警',
    desc: '切换至「执行记录」查看运行日志、耗时分布与健康状态（健康/需关注/异常），支持一键重试与异常告警排查。',
    tag: '监控治理',
    tagClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    iconBg: 'bg-emerald-600 text-white font-bold',
    actionText: '执行记录',
    actionType: 'history' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  }
]

const handleAction = (type: 'create' | 'agents' | 'history' | null) => {
  if (!type) return
  if (type === 'create') {
    emit('action', 'create')
  } else if (type === 'agents') {
    router.push('/dashboard/agent-management')
  } else if (type === 'history') {
    emit('action', 'history')
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
    aria-label="任务调度台全流程指引"
    class="relative overflow-hidden rounded-2xl border border-orange-100 bg-gradient-to-r from-orange-50/70 via-amber-50/40 to-slate-50/60 p-4 shadow-sm transition-all sm:p-5"
  >
    <!-- 背景光晕装饰 -->
    <div
      class="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-orange-200/30 blur-3xl"
      aria-hidden="true"
    ></div>
    <div
      class="pointer-events-none absolute left-1/3 -bottom-20 h-40 w-40 rounded-full bg-amber-200/25 blur-2xl"
      aria-hidden="true"
    ></div>

    <!-- 顶部标题与控制栏 -->
    <div class="relative z-10 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-orange-600 text-white shadow-md shadow-orange-600/30"
          style="background-color: #ea580c; color: #ffffff;"
        >
          <svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-bold text-gray-900 sm:text-base">
              任务调度台全流程构建指引
            </h3>
            <span
              class="rounded-full bg-orange-100/80 px-2 py-0.5 text-[11px] font-semibold text-orange-700"
            >
              5 步自动化闭环
            </span>
          </div>
          <p class="mt-0.5 text-xs text-gray-500">
            从 Cron 定时周期编排、资源与安全审批限定，到多渠道分发触达、Session Trace 时序观测与健康监控
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
        class="group relative flex flex-col justify-between rounded-xl border border-white/80 bg-white/85 p-3 shadow-2xs backdrop-blur-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-orange-200 hover:bg-white hover:shadow-md"
      >
        <!-- 连接箭头（仅在桌面端第 1~4 步显示） -->
        <div
          v-if="idx < steps.length - 1"
          class="pointer-events-none absolute -right-2 top-1/2 z-20 hidden -translate-y-1/2 text-orange-300 lg:block"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7" />
          </svg>
        </div>

        <div>
          <!-- 卡片头部：序号与标签 -->
          <div class="flex items-start justify-between gap-1.5">
            <div class="flex items-center gap-1.5 min-w-0">
              <span
                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold shadow-2xs"
                :class="item.iconBg"
              >
                {{ item.step }}
              </span>
              <span class="text-xs font-bold text-gray-900 leading-tight truncate" :title="item.title">{{ item.title }}</span>
            </div>
            <span
              class="rounded-md border px-1.5 py-0.5 text-[10px] font-semibold shrink-0 whitespace-nowrap leading-none"
              :class="item.tagClass"
            >
              {{ item.tag }}
            </span>
          </div>

          <!-- 副标题与说明文案 -->
          <div class="mt-2.5">
            <p class="text-[11px] font-medium text-orange-900/80">{{ item.subtitle }}</p>
            <p class="mt-1 text-[11px] leading-relaxed text-gray-500">{{ item.desc }}</p>
          </div>
        </div>

        <!-- 底部快捷动作 -->
        <div class="mt-3.5 border-t border-gray-100/80 pt-2.5">
          <div v-if="item.actionType" class="flex items-center gap-1.5">
            <button
              type="button"
              class="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-orange-200 bg-orange-50/60 py-1 text-xs font-medium text-orange-700 hover:bg-orange-600 hover:text-white transition-colors cursor-pointer"
              @click="handleAction(item.actionType)"
            >
              <span>{{ item.actionText }}</span>
              <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </button>
            <button
              v-if="item.secondaryActionType"
              type="button"
              class="inline-flex items-center justify-center rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 transition-colors cursor-pointer"
              :title="item.secondaryActionText || undefined"
              @click="handleAction(item.secondaryActionType)"
            >
              <span>{{ item.secondaryActionText }}</span>
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
