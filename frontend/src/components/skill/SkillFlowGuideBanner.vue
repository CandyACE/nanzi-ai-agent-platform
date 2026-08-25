<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const emit = defineEmits<{
  (e: 'action', type: 'create' | 'review' | 'global'): void
  (e: 'close'): void
  (e: 'dismiss'): void
}>()

const router = useRouter()
const isCollapsed = ref(true)

const steps = [
  {
    step: 1,
    title: '技能创建与目录规划',
    subtitle: 'SKILL.md 与 YAML 声明',
    desc: '设定英文 ID、中文名称与业务描述（Description 是大模型识别调用意图的关键）；自动生成 SKILL.md 入口。',
    tag: '规范创建',
    tagClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    iconBg: 'bg-emerald-600 text-white font-bold',
    actionText: '新建技能',
    actionType: 'create' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 2,
    title: '脚本编写与沙箱调试',
    subtitle: '多文件目录与代码实现',
    desc: '在内置工作台编写多级文件树（scripts/ 脚本、resources/ 模板、references/ 规范）；支持 Markdown 在线预览。',
    tag: '开发沉淀',
    tagClass: 'bg-blue-50 text-blue-700 border-blue-200',
    iconBg: 'bg-blue-600 text-white font-bold',
    actionText: '',
    actionType: null,
    hintText: '点击卡片进入文件树编辑',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 3,
    title: '提审申请与平台合规',
    subtitle: '申请发布与管理员审核',
    desc: '个人技能成熟后在抽屉中点击「申请发布至平台」；管理员在「待审核」Tab 下审查文件 Diff 与代码合规性。',
    tag: '提审合规',
    tagClass: 'bg-amber-50 text-amber-700 border-amber-200',
    iconBg: 'bg-amber-600 text-white font-bold',
    actionText: '前往待审核',
    actionType: 'review' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 4,
    title: '平台发布与版本隔离',
    subtitle: '全员共享与多版本基线',
    desc: '审批通过后晋升为平台公共技能，对全体业务角色公开；严格实现生产发布版本与开发草稿隔离，互不干扰。',
    tag: '生产就绪',
    tagClass: 'bg-purple-50 text-purple-700 border-purple-200',
    iconBg: 'bg-purple-600 text-white font-bold',
    actionText: '平台技能',
    actionType: 'global' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  },
  {
    step: 5,
    title: '智能体绑定与动态激活',
    subtitle: '多智能体装配与意图调度',
    desc: '在智能体中心为目标助手显式勾选挂载该技能，或由大模型意图感知动态加载；支持查看智能体使用分布。',
    tag: '生产消费',
    tagClass: 'bg-teal-50 text-teal-700 border-teal-200',
    iconBg: 'bg-teal-600 text-white font-bold',
    actionText: '前往智能体中心',
    actionType: 'agents' as const,
    hintText: '',
    secondaryActionText: null,
    secondaryActionType: null
  }
]

const handleAction = (type: 'create' | 'review' | 'global' | 'agents' | null) => {
  if (!type) return
  if (type === 'create') {
    emit('action', 'create')
  } else if (type === 'review') {
    emit('action', 'review')
  } else if (type === 'global') {
    emit('action', 'global')
  } else if (type === 'agents') {
    router.push('/dashboard/agent-management')
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
    aria-label="技能工作台全流程指引"
    class="relative overflow-hidden rounded-2xl border border-emerald-100 bg-gradient-to-r from-emerald-50/70 via-teal-50/40 to-slate-50/60 p-4 shadow-sm transition-all sm:p-5"
  >
    <!-- 背景光晕装饰 -->
    <div
      class="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-emerald-200/30 blur-3xl"
      aria-hidden="true"
    ></div>
    <div
      class="pointer-events-none absolute left-1/3 -bottom-20 h-40 w-40 rounded-full bg-teal-200/25 blur-2xl"
      aria-hidden="true"
    ></div>

    <!-- 顶部标题与控制栏 -->
    <div class="relative z-10 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-md shadow-emerald-600/30"
          style="background-color: #059669; color: #ffffff;"
        >
          <svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-bold text-gray-900 sm:text-base">
              技能工作台全生命周期研发指引
            </h3>
            <span
              class="rounded-full bg-emerald-100/80 px-2 py-0.5 text-[11px] font-semibold text-emerald-700"
            >
              5 步研发体系
            </span>
          </div>
          <p class="mt-0.5 text-xs text-gray-500">
            从 SKILL.md 规范定义、代码脚本沉淀，到发布审批、平台多版本隔离与智能体动态装配激活
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
        class="group relative flex flex-col justify-between rounded-xl border border-white/80 bg-white/85 p-3 shadow-2xs backdrop-blur-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-emerald-200 hover:bg-white hover:shadow-md"
      >
        <!-- 连接箭头（仅在桌面端第 1~4 步显示） -->
        <div
          v-if="idx < steps.length - 1"
          class="pointer-events-none absolute -right-2 top-1/2 z-20 hidden -translate-y-1/2 text-emerald-300 lg:block"
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
            <p class="text-[11px] font-medium text-emerald-900/80">{{ item.subtitle }}</p>
            <p class="mt-1 text-[11px] leading-relaxed text-gray-500">{{ item.desc }}</p>
          </div>
        </div>

        <!-- 底部快捷动作 -->
        <div class="mt-3.5 border-t border-gray-100/80 pt-2.5">
          <div v-if="item.actionType" class="flex items-center gap-1.5">
            <button
              type="button"
              class="inline-flex flex-1 items-center justify-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50/60 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-600 hover:text-white transition-colors cursor-pointer"
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
