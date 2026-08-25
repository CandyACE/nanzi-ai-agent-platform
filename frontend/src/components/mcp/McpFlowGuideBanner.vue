<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const emit = defineEmits<{
  (e: 'action', type: 'add' | 'marketplace'): void
  (e: 'close'): void
  (e: 'dismiss'): void
}>()

const router = useRouter()
const isCollapsed = ref(true)

const steps = [
  {
    step: 1,
    title: '服务登记与生态安装',
    subtitle: 'SSE/Stdio/生态市场',
    desc: '支持接入 SSE 远程长连接服务、Stdio 本地进程或一键粘贴 JSON 配置；支持从生态市场一键安装官方精选服务。',
    tag: '服务接入',
    tagClass: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    iconBg: 'bg-indigo-600 text-white font-bold',
    actionText: '新增服务',
    actionType: 'add' as const,
    hintText: '',
    secondaryActionText: '生态市场',
    secondaryActionType: 'marketplace' as const
  },
  {
    step: 2,
    title: '探活发现与工具同步',
    subtitle: 'tools/list 自动提取入参',
    desc: '系统自动发起 tools/list 协议握手与健康检查，自动解析工具名称、描述与 JSON Schema 入参定义；支持一键刷新同步。',
    tag: '协议自检',
    tagClass: 'bg-blue-50 text-blue-700 border-blue-200',
    iconBg: 'bg-blue-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '服务列表点击刷新即刻同步',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 3,
    title: '在线测试与参数调试',
    subtitle: '内置沙箱实时参数验证',
    desc: '点击服务卡片中各工具的「测试」按钮进入调试台，输入测试值实时触发 MCP 执行并查看原始返回，快速排查网络和鉴权。',
    tag: '沙箱验证',
    tagClass: 'bg-teal-50 text-teal-700 border-teal-200',
    iconBg: 'bg-teal-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '卡片中点击测试按钮验证',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 4,
    title: '范围隔离与权限分配',
    subtitle: '平台共享与个人私有隔离',
    desc: '区分「平台公开 MCP」（全员可用，需管理员维护）与「我的私有 MCP」（个人专属）；在角色管理中下发操作与维护权限。',
    tag: '安全治理',
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
    title: '智能体挂载与协同调用',
    subtitle: '多智能体生态生产落地',
    desc: '前往「智能体中心」在目标智能体版本装配中显式勾选挂载该 MCP 服务；智能体在对话中自主调度 MCP 执行复杂任务。',
    tag: '落地消费',
    tagClass: 'bg-amber-50 text-amber-700 border-amber-200',
    iconBg: 'bg-amber-600 text-white font-bold',
    actionText: '前往智能体中心',
    actionType: 'agents' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  }
]

const handleAction = (type: 'add' | 'marketplace' | 'roles' | 'agents' | null) => {
  if (!type) return
  if (type === 'roles') {
    router.push('/dashboard/roles')
  } else if (type === 'agents') {
    router.push('/dashboard/agent-management')
  } else if (type === 'add') {
    emit('action', 'add')
  } else if (type === 'marketplace') {
    emit('action', 'marketplace')
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
    aria-label="MCP 工具集全流程指引"
    class="relative overflow-hidden rounded-2xl border border-indigo-100 bg-gradient-to-r from-indigo-50/70 via-blue-50/40 to-slate-50/60 p-4 shadow-sm transition-all sm:p-5"
  >
    <!-- 背景光晕装饰 -->
    <div
      class="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-indigo-200/30 blur-3xl"
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
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
          style="background-color: #4f46e5; color: #ffffff;"
        >
          <svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z" />
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-bold text-gray-900 sm:text-base">
              MCP 工具集全生命周期接入指引
            </h3>
            <span
              class="rounded-full bg-indigo-100/80 px-2 py-0.5 text-[11px] font-semibold text-indigo-700"
            >
              5 步实施标准
            </span>
          </div>
          <p class="mt-0.5 text-xs text-gray-500">
            从服务登记与生态市场安装、tools/list 探活自发现，到沙箱测试、权限范围隔离与智能体装配调用
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
        class="group relative flex flex-col justify-between rounded-xl border border-white/80 bg-white/85 p-3 shadow-2xs backdrop-blur-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-indigo-200 hover:bg-white hover:shadow-md"
      >
        <!-- 连接箭头（仅在桌面端第 1~4 步显示） -->
        <div
          v-if="idx < steps.length - 1"
          class="pointer-events-none absolute -right-2 top-1/2 z-20 hidden -translate-y-1/2 text-indigo-300 lg:block"
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
            <p class="text-[11px] font-medium text-indigo-900/80">{{ item.subtitle }}</p>
            <p class="mt-1 text-[11px] leading-relaxed text-gray-500">{{ item.desc }}</p>
          </div>
        </div>

        <!-- 底部快捷动作 -->
        <div class="mt-3.5 border-t border-gray-100/80 pt-2.5">
          <div v-if="item.actionType" class="flex items-center gap-1.5">
            <button
              type="button"
              class="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50/60 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-600 hover:text-white transition-colors cursor-pointer"
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
