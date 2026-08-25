<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const emit = defineEmits<{
  (e: 'action', type: 'create' | 'template' | 'skills'): void
  (e: 'close'): void
  (e: 'dismiss'): void
}>()

const router = useRouter()
const isCollapsed = ref(true)

const steps = [
  {
    step: 1,
    title: '定义与系统标识',
    subtitle: '设定业务定位与路由依据',
    desc: '填写名称与业务描述。提示：仅勾选「系统智能体」才能参与多智能体协同主路由自动分派；支持从场景模板克隆。',
    tag: '基础准备',
    tagClass: 'bg-blue-50 text-blue-700 border-blue-200',
    iconBg: 'bg-blue-600 text-white font-bold',
    actionText: '新建智能体',
    actionType: 'create' as const,
    hintText: '',
    secondaryActionText: '场景模板',
    secondaryActionType: 'template' as const
  },
  {
    step: 2,
    title: '模型与能力装配',
    subtitle: '整合 Prompt、工具与技能',
    desc: '配置模型底座与提示词，按需装配内置 API 工具、MCP 外部服务、动态 Skills 以及挂载数据集/知识库。',
    tag: '资源整合',
    tagClass: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    iconBg: 'bg-indigo-600 text-white font-bold',
    actionText: '技能工作台',
    actionType: 'skills' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 3,
    title: '版本管理与发布',
    subtitle: '多版本隔离与就绪度校验',
    desc: '草稿 (DRAFT) 与生产发布隔离。系统自动校验主类型、工具链与数据绑定就绪度，一键发布即刻生效。',
    tag: '质量基线',
    tagClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    iconBg: 'bg-emerald-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '点击卡片管理版本',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 4,
    title: '角色授权与权限',
    subtitle: '下发角色权限确保可访问',
    desc: '在角色管理中为目标业务角色授予该智能体的交互权限。未授权角色的普通用户将无法在工作台查看或调用。',
    tag: '权限受控',
    tagClass: 'bg-purple-50 text-purple-700 border-purple-200',
    iconBg: 'bg-purple-600 text-white font-bold',
    actionText: '前往角色管理',
    actionType: 'roles' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 5,
    title: '调试与渠道消费',
    subtitle: '时序跟踪与全渠道落地',
    desc: '在调试台观察思考链与工具调用；系统智能体自动加入意图路由；支持生成 Embed 对话或对接钉钉/企微。',
    tag: '消费应用',
    tagClass: 'bg-amber-50 text-amber-700 border-amber-200',
    iconBg: 'bg-amber-600 text-white font-bold',
    actionText: '去智能体调试',
    actionType: 'debug' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  }
]

const handleAction = (type: 'create' | 'template' | 'skills' | 'roles' | 'debug' | null) => {
  if (!type) return
  if (type === 'roles') {
    router.push('/dashboard/roles')
  } else if (type === 'debug') {
    router.push('/dashboard/agent-debug')
  } else if (type === 'template') {
    router.push('/dashboard/scenario-templates')
  } else if (type === 'skills') {
    router.push('/dashboard/skills')
  } else if (type === 'create') {
    emit('action', 'create')
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
    aria-label="智能体中心全流程指引"
    class="relative overflow-hidden rounded-2xl border border-blue-100 bg-gradient-to-r from-blue-50/70 via-indigo-50/40 to-slate-50/60 p-4 shadow-sm transition-all sm:p-5"
  >
    <!-- 背景光晕装饰 -->
    <div
      class="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-blue-200/30 blur-3xl"
      aria-hidden="true"
    ></div>
    <div
      class="pointer-events-none absolute left-1/3 -bottom-20 h-40 w-40 rounded-full bg-indigo-200/25 blur-2xl"
      aria-hidden="true"
    ></div>

    <!-- 顶部标题与控制栏 -->
    <div class="relative z-10 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white shadow-md shadow-blue-600/30"
          style="background-color: #2563eb; color: #ffffff;"
        >
          <svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-bold text-gray-900 sm:text-base">
              智能体全流程构建指引
            </h3>
            <span
              class="rounded-full bg-blue-100/80 px-2 py-0.5 text-[11px] font-semibold text-blue-700"
            >
              5 步生命周期
            </span>
          </div>
          <p class="mt-0.5 text-xs text-gray-500">
            从角色定位、大模型与技能装配，到版本发布、权限分配与全渠道消费
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
        class="group relative flex flex-col justify-between rounded-xl border border-white/80 bg-white/85 p-3 shadow-2xs backdrop-blur-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-200 hover:bg-white hover:shadow-md"
      >
        <!-- 连接箭头（仅在桌面端第 1~4 步显示） -->
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
            <p class="text-[11px] font-medium text-blue-900/80">{{ item.subtitle }}</p>
            <p class="mt-1 text-[11px] leading-relaxed text-gray-500">{{ item.desc }}</p>
          </div>
        </div>

        <!-- 底部快捷动作 -->
        <div class="mt-3.5 border-t border-gray-100/80 pt-2.5">
          <div v-if="item.actionType" class="flex items-center gap-1.5">
            <button
              type="button"
              class="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-blue-200 bg-blue-50/50 py-1 text-xs font-medium text-blue-700 hover:bg-blue-600 hover:text-white transition-colors cursor-pointer"
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
