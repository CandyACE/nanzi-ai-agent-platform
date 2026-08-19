<template>
  <teleport to="body">
    <div
      v-if="visible"
      :class="[
        pinned
          ? 'fixed inset-y-0 right-0 z-[145] flex pointer-events-none'
          : 'fixed inset-0 z-[145] overflow-hidden',
      ]"
    >
      <div
        v-if="!pinned"
        class="absolute inset-0 bg-gray-500/30 backdrop-blur-[1px]"
        @click="emit('close')"
      />
      <aside
        :class="[
          pinned
            ? 'h-full flex pointer-events-auto'
            : 'absolute inset-y-0 right-0 flex w-full max-w-full sm:w-auto',
        ]"
      >
        <section
          :style="panelStyle"
          :class="[
            'relative z-10 flex min-h-0 flex-col border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-900',
            isResizing ? 'select-none transition-none' : 'transition-all duration-300',
            isMobile
              ? 'h-full w-full border-0'
              : 'h-full w-screen max-w-[calc(100vw-300px)] border-l',
          ]"
          aria-label="服务端浏览器"
        >
          <div v-if="isResizing" class="fixed inset-0 z-[300] cursor-col-resize select-none" />
          <div
            v-if="showCloseSessionConfirm"
            class="absolute inset-0 z-[260] flex items-center justify-center bg-slate-950/30 p-4"
            @click.self="showCloseSessionConfirm = false"
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="browser-close-session-title"
              class="w-full max-w-sm rounded-xl border border-gray-200 bg-white p-4 shadow-2xl dark:border-gray-700 dark:bg-gray-900"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div id="browser-close-session-title" class="text-sm font-bold text-gray-900 dark:text-gray-100">结束浏览器会话？</div>
                  <div class="mt-1 text-xs leading-relaxed text-gray-500 dark:text-gray-400">远程浏览器会关闭，Profile 和 Cookie 会保留，下次可以重新打开。</div>
                </div>
                <button
                  type="button"
                  class="rounded-md px-1.5 py-0.5 text-lg leading-none text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-200"
                  aria-label="关闭确认弹窗"
                  title="关闭确认弹窗"
                  @click="showCloseSessionConfirm = false"
                >
                  ×
                </button>
              </div>
              <div class="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  class="rounded-md border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                  @click="showCloseSessionConfirm = false"
                >
                  取消
                </button>
                <button
                  type="button"
                  class="rounded-md bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700"
                  @click="confirmCloseSession"
                >
                  结束会话
                </button>
              </div>
            </div>
          </div>
          <div
            v-if="!isMobile"
            class="absolute bottom-0 left-0 top-0 z-50 flex w-3 -translate-x-1/2 cursor-col-resize select-none items-center justify-center touch-none"
            :class="isResizing ? 'bg-primary/30' : 'hover:bg-primary/20'"
            title="左右拖拽调整浏览器宽度（双击重置）"
            @mousedown="startResize"
            @dblclick="resetWidth"
          >
            <div
              class="flex h-8 w-1 flex-col items-center justify-center gap-0.5 rounded-full transition-all"
              :class="isResizing ? 'scale-110 bg-primary shadow-sm' : 'bg-gray-300 group-hover:bg-primary dark:bg-gray-600'"
            >
              <div class="h-0.5 w-0.5 rounded-full bg-white dark:bg-gray-900" />
              <div class="h-0.5 w-0.5 rounded-full bg-white dark:bg-gray-900" />
              <div class="h-0.5 w-0.5 rounded-full bg-white dark:bg-gray-900" />
            </div>
          </div>
          <header class="relative flex h-12 shrink-0 items-center justify-between border-b border-gray-200 px-3 dark:border-gray-700">
            <div class="flex min-w-0 items-center gap-2">
              <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-300">⌁</span>
              <div class="min-w-0">
                <div class="truncate text-xs font-bold text-gray-800 dark:text-gray-100">服务端浏览器</div>
                <div class="flex items-center gap-1.5 text-[10px] text-gray-400">
                  <span :class="connected ? 'bg-emerald-500' : 'bg-amber-500'" class="h-1.5 w-1.5 rounded-full" />
                  {{ connected ? '已连接，可人工接管' : loadingStage }}
                </div>
              </div>
            </div>
            <div class="flex items-center gap-1.5">
              <span v-if="pinned && !isMobile" class="hidden rounded bg-blue-50 px-1.5 py-0.5 text-[9px] font-bold text-blue-600 dark:bg-blue-500/10 dark:text-blue-300 sm:inline-flex">已钉住</span>
              <button
                v-if="sessionId"
                type="button"
                class="rounded-md px-1.5 py-1 text-[10px] font-semibold text-gray-500 hover:bg-red-50 hover:text-red-600 dark:text-gray-400 dark:hover:bg-red-950/30 dark:hover:text-red-300"
                title="结束当前浏览器会话（保留 Profile 和 Cookie）"
                @click="showCloseSessionConfirm = true"
              >
                结束会话
              </button>
              <button
                v-if="!isMobile"
                type="button"
                class="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-blue-600 dark:hover:bg-gray-800 dark:hover:text-blue-300"
                :class="pinned ? 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300' : ''"
                :title="pinned ? '取消钉住' : '钉住浏览器面板'"
                :aria-label="pinned ? '取消钉住' : '钉住浏览器面板'"
                @click="pinned = !pinned"
              >
                <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 17v5" /><path d="M9 10.7a2 2 0 0 1-1.1 1.8l-1.8.9A2 2 0 0 0 5 15.2V16h14v-.8a2 2 0 0 0-1.1-1.8l-1.8-.9A2 2 0 0 1 15 10.7V7a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v3.7Z" />
                </svg>
              </button>
              <select
                :value="approvalMode"
                class="rounded-md border px-1.5 py-1 text-[10px] font-semibold outline-none transition-colors dark:bg-gray-800 dark:text-gray-200"
                :class="approvalMode === 'guarded'
                  ? 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200'
                  : 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200'"
                title="浏览器动作模式"
                @change="emit('update:approval-mode', ($event.target as HTMLSelectElement).value as ApprovalMode)"
              >
                <option value="guarded">安全确认</option>
                <option value="autopilot">自动执行</option>
              </select>
              <button class="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-800" title="关闭浏览器" @click="emit('close')">×</button>
            </div>
          </header>

          <div
            v-if="approvalMode === 'guarded' && showSafetyNotice"
            role="status"
            class="absolute right-3 top-14 z-40 flex w-[min(320px,calc(100%-24px))] items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2.5 text-amber-950 shadow-lg shadow-amber-900/10 dark:border-amber-700 dark:bg-amber-950/80 dark:text-amber-100"
          >
            <span class="mt-0.5 text-sm" aria-hidden="true">⚠️</span>
            <div class="min-w-0 flex-1">
              <div class="text-[11px] font-extrabold">安全确认已开启</div>
              <div class="mt-0.5 text-[10px] leading-relaxed text-amber-800 dark:text-amber-200">提交、删除、支付等高风险动作会等待你的确认。</div>
            </div>
            <button
              type="button"
              class="rounded p-0.5 text-amber-700 hover:bg-amber-200 hover:text-amber-950 dark:text-amber-200 dark:hover:bg-amber-800 dark:hover:text-white"
              aria-label="关闭安全提示"
              title="关闭安全提示"
              @click="showSafetyNotice = false"
            >
              ×
            </button>
          </div>

          <div class="flex shrink-0 items-center gap-2 border-b border-gray-100 px-3 py-2 dark:border-gray-800">
            <input
              v-model="address"
              class="min-w-0 flex-1 rounded-md border border-gray-200 bg-gray-50 px-2 py-1.5 text-[11px] text-gray-700 outline-none focus:border-blue-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              placeholder="输入网址，如 www.baidu.com"
              @keyup.enter="navigate"
            />
            <button class="rounded-md bg-blue-600 px-2.5 py-1.5 text-[10px] font-bold text-white hover:bg-blue-700" @click="navigate">打开</button>
          </div>

          <div class="flex shrink-0 items-center justify-between gap-3 border-b border-sky-100 bg-sky-50 px-3 py-1.5 text-[10px] text-sky-900 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-100">
            <div class="flex min-w-0 items-center gap-1.5">
              <span aria-hidden="true">▧</span>
              <strong class="shrink-0 font-bold">远程页面截图</strong>
              <span class="truncate text-sky-700 dark:text-sky-200">不是网页本体；点击、滚轮、键盘会转发到远程浏览器</span>
            </div>
            <div class="flex shrink-0 items-center gap-1.5">
              <span class="text-sky-600 dark:text-sky-300">
                {{ controlOwner === 'human' ? '当前由人工操作，自动刷新已暂停' : captchaDetected ? '验证码处理中，自动刷新已暂停' : interactionInProgress ? '操作中，完成后刷新一次' : autoRefreshPaused ? '自动刷新已暂停' : '每 5 秒自动刷新' }}
              </span>
              <button
                v-if="controlOwner !== 'human' && !captchaDetected && !interactionInProgress"
                type="button"
                class="rounded border border-sky-200 bg-white/70 px-1.5 py-0.5 font-semibold text-sky-700 hover:bg-white dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-200 dark:hover:bg-sky-900/60"
                @click="autoRefreshPaused ? resumeAutoRefresh() : pauseAutoRefresh()"
              >
                {{ autoRefreshPaused ? '恢复自动刷新' : '暂停刷新' }}
              </button>
            </div>
          </div>

          <div
            ref="viewportRef"
            class="relative min-h-0 flex-1 overflow-auto bg-slate-100 p-2 dark:bg-slate-950"
            tabindex="0"
            @keydown="handleKeydown"
            @wheel.prevent="handleWheel"
          >
            <div v-if="errorMessage" class="mb-2 rounded-md border border-red-200 bg-red-50 px-2 py-1.5 text-[11px] text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
              {{ errorMessage }}
            </div>
            <div v-if="remoteFocusMessage" class="mb-2 flex items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-2 py-1.5 text-[10px] text-blue-800 dark:border-blue-900/60 dark:bg-blue-950/30 dark:text-blue-200" role="status">
              <span aria-hidden="true">🎯</span>
              <span>{{ remoteFocusMessage }}</span>
            </div>
            <div
              v-if="controlOwner === 'human'"
              class="mb-2 flex items-center justify-between gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-[10px] text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200"
              role="status"
            >
              <span
                class="min-w-0 truncate"
                :title="controlReason ? `人工接管：${controlReason}` : '当前由人工操作'"
              >
                <strong>当前由人工操作</strong>
                <span v-if="captchaDetected">，请完成安全验证</span>
              </span>
              <button
                type="button"
                class="shrink-0 rounded border border-emerald-300 bg-white/70 px-2 py-0.5 font-semibold text-emerald-700 hover:bg-white dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
                @click="releaseControl"
              >
                交还 AI
              </button>
            </div>
            <div v-if="screenshotUrl" class="pointer-events-none absolute bottom-3 left-3 z-10" role="note">
              <span class="rounded-md border border-red-300 bg-white/90 px-2.5 py-1 text-[11px] font-bold text-red-600 shadow-sm dark:border-red-700 dark:bg-red-950/90 dark:text-red-300">
                这是页面截图，非 HTML 页面
              </span>
            </div>
            <div v-if="screenshotUrl" class="relative">
              <img
                :key="snapshot.snapshot_id"
                :src="screenshotUrl"
                alt="远程浏览器画面"
                draggable="false"
                class="block w-full cursor-crosshair select-none touch-none rounded border border-gray-200 bg-white shadow-sm dark:border-gray-700"
                @click="handleImageClick"
                @pointerdown="handleImagePointerDown"
                @pointermove="handleImagePointerMove"
                @pointerup="handleImagePointerUp"
                @pointercancel="handleImagePointerCancel"
              />
            </div>
            <div v-else class="flex h-full min-h-56 items-center justify-center px-6 text-center text-xs text-gray-400">
              <div class="w-full max-w-sm rounded-xl border border-sky-100 bg-white/80 p-5 shadow-sm dark:border-sky-900/60 dark:bg-gray-900/70">
                <div class="mx-auto mb-4 h-2 w-32 animate-pulse rounded-full bg-sky-100 dark:bg-sky-900/60" />
                <div class="mx-auto h-2 w-56 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700" />
                <div class="mx-auto mt-2 h-2 w-44 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700" />
                <div class="mt-4 font-semibold text-slate-600 dark:text-slate-300">{{ loadingStage }}</div>
                <div class="mt-1 text-[10px] text-slate-400 dark:text-slate-500">页面加载完成后，画面会自动显示在这里</div>
              </div>
            </div>
          </div>

          <div
            v-if="showManualInput"
            class="absolute bottom-14 left-3 right-3 z-40 sm:left-auto sm:w-80"
            role="dialog"
            aria-label="人工输入"
          >
            <div class="rounded-xl border border-blue-200 bg-white p-3 shadow-xl shadow-blue-900/10 dark:border-blue-800 dark:bg-gray-900">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="text-xs font-bold text-gray-800 dark:text-gray-100">人工输入</div>
                  <div class="mt-0.5 text-[10px] leading-relaxed text-gray-500 dark:text-gray-400">已聚焦远程输入框，文字会发送到远程页面</div>
                </div>
                <button
                  type="button"
                  class="rounded p-0.5 text-base leading-none text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-200"
                  aria-label="关闭人工输入"
                  title="关闭人工输入"
                  @click="showManualInput = false"
                >
                  ×
                </button>
              </div>
              <div class="mt-2 flex gap-2">
                <input
                  ref="manualInputRef"
                  v-model="manualText"
                  type="text"
                  autocomplete="off"
                  class="min-w-0 flex-1 rounded-md border border-blue-200 bg-blue-50/40 px-2 py-1.5 text-xs outline-none focus:border-blue-400 dark:border-blue-800 dark:bg-blue-950/20 dark:text-gray-200"
                  placeholder="输入文字，回车发送"
                  @keyup.enter="sendText"
                  @keydown.esc="showManualInput = false"
                />
                <button class="rounded-md bg-blue-600 px-2.5 py-1.5 text-[10px] font-bold text-white hover:bg-blue-700" @click="sendText">发送</button>
              </div>
            </div>
          </div>

          <footer class="shrink-0 border-t border-gray-200 bg-white p-2 dark:border-gray-700 dark:bg-gray-900">
            <div class="mb-1 flex items-center justify-between text-[10px] text-gray-400">
              <span class="truncate">{{ snapshot?.title || '未加载页面' }}</span>
              <button class="shrink-0 text-blue-600 hover:underline dark:text-blue-300" @click="requestSnapshot">刷新画面</button>
            </div>
            <div class="text-[10px] leading-relaxed text-gray-400">可直接点击、拖拽截图，滚轮、输入文字或按键；点击输入框后会弹出人工输入，验证码请由人工完成。</div>
          </footer>
        </section>
      </aside>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

type ApprovalMode = 'guarded' | 'autopilot';
type ControlOwner = 'ai' | 'human';
type BrowserElement = {
  ref: string;
  role?: string | null;
  name?: string | null;
  value?: string | null;
  disabled?: boolean;
  sensitive?: boolean;
};
type BrowserSnapshot = {
  session_id: string;
  snapshot_id: string;
  tab_id?: string | null;
  url: string;
  title: string;
  screenshot_ref?: string | null;
  elements: BrowserElement[];
  scroll_x?: number;
  scroll_y?: number;
  viewport_width?: number | null;
  viewport_height?: number | null;
  document_width?: number | null;
  document_height?: number | null;
  page_text?: string;
  visible_text?: string;
};
type RemotePoint = { x: number; y: number };
const BROWSER_PANEL_REFRESH_INTERVAL_MS = 5000;

const props = defineProps<{
  visible: boolean;
  loading?: boolean;
  refreshSignal?: number;
  sessionId: string | null;
  viewerToken: string | null;
  approvalMode: ApprovalMode;
}>();

const pinned = defineModel<boolean>('pinned', { default: true });
const panelWidth = defineModel<number>('panelWidth', { default: 520 });

const emit = defineEmits<{
  (event: 'close'): void;
  (event: 'close-session'): void;
  (event: 'update:approval-mode', mode: ApprovalMode): void;
}>();

const showSafetyNotice = ref(props.approvalMode === 'guarded');
const showCloseSessionConfirm = ref(false);

const socket = ref<WebSocket | null>(null);
const connected = ref(false);
const snapshot = ref<BrowserSnapshot | null>(null);
const errorMessage = ref('');
const address = ref('');
const manualText = ref('');
const showManualInput = ref(false);
const manualInputRef = ref<HTMLInputElement | null>(null);
const remoteFocusMessage = ref('请先点击截图中的输入框，再使用下方人工输入');
const controlOwner = ref<ControlOwner>('ai');
const controlReason = ref<string | null>(null);
const captchaDetected = ref(false);
const interactionInProgress = ref(false);
const snapshotRequestInFlight = ref(false);
const pointerDownPoint = ref<RemotePoint | null>(null);
const lastPointerPoint = ref<RemotePoint | null>(null);
const pointerDragging = ref(false);
const suppressNextClick = ref(false);
let lastPointerMoveAt = 0;
const autoRefreshPaused = ref(false);
const viewportRef = ref<HTMLElement | null>(null);
const isMobile = ref(
  typeof window !== 'undefined' && window.matchMedia('(max-width: 639px)').matches,
);
let mobileMq: MediaQueryList | null = null;
const customWidth = ref<number | null>(null);
const isResizing = ref(false);
const BROWSER_PANEL_WIDTH_STORAGE_KEY = 'nanzi_browser_panel_width';

const syncMobile = () => {
  isMobile.value = !!mobileMq?.matches;
  if (isMobile.value) pinned.value = false;
};

const loadCustomWidth = () => {
  if (typeof window === 'undefined') return;
  const saved = localStorage.getItem(BROWSER_PANEL_WIDTH_STORAGE_KEY);
  if (!saved) return;
  const parsed = parseInt(saved, 10);
  if (!Number.isNaN(parsed) && parsed >= 360) {
    customWidth.value = parsed;
    panelWidth.value = parsed;
  }
};

const startResize = (event: MouseEvent) => {
  if (isMobile.value) return;
  event.preventDefault();
  isResizing.value = true;
  document.body.classList.add('select-none');
  window.addEventListener('mousemove', handleResizing);
  window.addEventListener('mouseup', stopResize);
};

const handleResizing = (event: MouseEvent) => {
  if (!isResizing.value) return;
  const viewportWidth = window.innerWidth;
  const minWidth = 360;
  const maxWidth = Math.min(760, Math.max(minWidth, viewportWidth - 300));
  const nextWidth = Math.min(maxWidth, Math.max(minWidth, viewportWidth - event.clientX));
  customWidth.value = nextWidth;
  panelWidth.value = nextWidth;
};

const stopResize = () => {
  if (!isResizing.value) return;
  isResizing.value = false;
  document.body.classList.remove('select-none');
  window.removeEventListener('mousemove', handleResizing);
  window.removeEventListener('mouseup', stopResize);
  if (customWidth.value) {
    localStorage.setItem(BROWSER_PANEL_WIDTH_STORAGE_KEY, String(customWidth.value));
  }
};

const resetWidth = () => {
  customWidth.value = null;
  panelWidth.value = 520;
  localStorage.removeItem(BROWSER_PANEL_WIDTH_STORAGE_KEY);
};

const panelStyle = computed(() => {
  if (isMobile.value) return {};
  const width = customWidth.value ?? panelWidth.value ?? 520;
  return {
    width: `${width}px`,
    maxWidth: 'calc(100vw - 300px)',
  };
});
const screenshotUrl = computed(() => {
  const reference = snapshot.value?.screenshot_ref;
  const snapshotId = snapshot.value?.snapshot_id;
  if (!reference || !snapshotId) return null;
  const separator = reference.includes('?') ? '&' : '?';
  return `${reference}${separator}snapshot_id=${encodeURIComponent(snapshotId)}`;
});
const loadingStage = computed(() => {
  if (props.loading && !props.sessionId) return '正在准备服务端浏览器…';
  if (props.loading && !props.viewerToken) return '正在连接浏览器服务…';
  if (!connected.value) return props.sessionId ? '正在连接实时画面…' : '等待浏览器会话…';
  if (!snapshot.value) return '正在获取页面截图…';
  return '页面已就绪';
});
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let pollTimer: ReturnType<typeof setInterval> | null = null;
let interactionFinishTimer: ReturnType<typeof setTimeout> | null = null;

const stopPolling = () => {
  if (!pollTimer) return;
  clearInterval(pollTimer);
  pollTimer = null;
};

const stopInteractionFinishTimer = () => {
  if (!interactionFinishTimer) return;
  clearTimeout(interactionFinishTimer);
  interactionFinishTimer = null;
};

const closeSocket = () => {
  connected.value = false;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  stopPolling();
  stopInteractionFinishTimer();
  interactionInProgress.value = false;
  snapshotRequestInFlight.value = false;
  if (socket.value) {
    socket.value.onclose = null;
    socket.value.close();
    socket.value = null;
  }
};

const connect = async () => {
  closeSocket();
  snapshot.value = null;
  errorMessage.value = '';
  showManualInput.value = false;
  manualText.value = '';
  controlOwner.value = 'ai';
  controlReason.value = null;
  captchaDetected.value = false;
  interactionInProgress.value = false;
  if (!props.visible || !props.sessionId || !props.viewerToken || typeof window === 'undefined') return;
  await nextTick();
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${scheme}//${window.location.host}/api/v1/chat/browser/sessions/${encodeURIComponent(props.sessionId)}/viewer`;
  const client = new WebSocket(url, [`browser-viewer.${props.viewerToken}`]);
  socket.value = client;
  client.onopen = () => {
    if (socket.value !== client) return;
    connected.value = true;
    startPolling();
  };
  client.onmessage = (event) => {
    if (socket.value !== client) return;
    let payload: {
      type?: string;
      snapshot?: BrowserSnapshot;
      message?: string;
      focused_input?: boolean;
      owner?: ControlOwner;
      reason?: string | null;
      captcha?: boolean;
      detected?: boolean;
    };
    try {
      payload = JSON.parse(event.data) as {
        type?: string;
        snapshot?: BrowserSnapshot;
        message?: string;
        focused_input?: boolean;
        owner?: ControlOwner;
        reason?: string | null;
        captcha?: boolean;
        detected?: boolean;
      };
    } catch {
      errorMessage.value = '浏览器返回了无法识别的消息';
      return;
    }
    if (payload.type === 'control_state') {
      controlOwner.value = payload.owner === 'human' ? 'human' : 'ai';
      controlReason.value = payload.reason || null;
      if (controlOwner.value === 'human') {
        stopPolling();
      } else if (payload.captcha) {
        captchaDetected.value = true;
        stopPolling();
      } else if (!interactionInProgress.value && !autoRefreshPaused.value && !pollTimer) {
        startPolling();
      }
    } else if (payload.type === 'captcha') {
      captchaDetected.value = Boolean(payload.detected);
      if (captchaDetected.value) {
        stopPolling();
        remoteFocusMessage.value = '检测到安全验证，请人工完成；自动刷新已暂停';
      } else if (controlOwner.value === 'human') {
        stopPolling();
      } else if (!interactionInProgress.value && !autoRefreshPaused.value && !pollTimer) {
        startPolling();
      }
    } else if (payload.type === 'focus') {
      showManualInput.value = Boolean(payload.focused_input);
      if (showManualInput.value) {
        remoteFocusMessage.value = '已聚焦输入区域，请在弹框中输入文字';
        void nextTick(() => manualInputRef.value?.focus());
      } else {
        manualText.value = '';
        remoteFocusMessage.value = '当前点击的不是输入框';
      }
    } else if (payload.type === 'snapshot' && payload.snapshot) {
      snapshotRequestInFlight.value = false;
      const previousUrl = snapshot.value?.url;
      snapshot.value = payload.snapshot;
      address.value = payload.snapshot.url || address.value;
      if (payload.snapshot.page_state === 'captcha') {
        captchaDetected.value = true;
        stopPolling();
      }
      if (previousUrl && previousUrl !== payload.snapshot.url) {
        showManualInput.value = false;
        manualText.value = '';
        remoteFocusMessage.value = '页面已变化，请重新点击要输入的区域';
      }
    } else if (payload.type === 'error') {
      snapshotRequestInFlight.value = false;
      errorMessage.value = payload.message || '浏览器操作失败';
    }
  };
  client.onerror = () => {
    if (socket.value !== client) return;
    errorMessage.value = '浏览器连接失败，请稍后重试';
  };
  client.onclose = () => {
    if (socket.value !== client) return;
    connected.value = false;
    snapshotRequestInFlight.value = false;
    errorMessage.value = '浏览器连接已断开，正在重连…';
    if (props.visible && socket.value === client) {
      reconnectTimer = setTimeout(() => void connect(), 1500);
    }
  };
};

const send = (payload: Record<string, unknown>): boolean => {
  if (socket.value?.readyState === WebSocket.OPEN) {
    socket.value.send(JSON.stringify(payload));
    return true;
  }
  return false;
};

const requestSnapshot = () => {
  if (!connected.value) return;
  if (snapshotRequestInFlight.value) return;
  snapshotRequestInFlight.value = true;
  if (!send({ type: 'snapshot' })) {
    snapshotRequestInFlight.value = false;
  }
};

const startPolling = () => {
  stopPolling();
  if (controlOwner.value === 'human' || autoRefreshPaused.value || interactionInProgress.value || captchaDetected.value || !connected.value) return;
  pollTimer = setInterval(requestSnapshot, BROWSER_PANEL_REFRESH_INTERVAL_MS);
};

const pauseAutoRefresh = () => {
  autoRefreshPaused.value = true;
  stopPolling();
};

const resumeAutoRefresh = () => {
  autoRefreshPaused.value = false;
  if (!connected.value || captchaDetected.value || interactionInProgress.value) return;
  requestSnapshot();
  startPolling();
};

const pauseForInteraction = () => {
  interactionInProgress.value = true;
  controlOwner.value = 'human';
  stopPolling();
};

const finishInteraction = () => {
  stopInteractionFinishTimer();
  if (!interactionInProgress.value) return;
  interactionInProgress.value = false;
};

const scheduleInteractionFinish = () => {
  stopInteractionFinishTimer();
  interactionFinishTimer = setTimeout(finishInteraction, 180);
};

const releaseControl = () => {
  send({ type: 'release_control' });
  remoteFocusMessage.value = '正在交还 AI 控制权';
  if (!captchaDetected.value && !autoRefreshPaused.value && controlOwner.value === 'ai') startPolling();
};

const confirmCloseSession = () => {
  showCloseSessionConfirm.value = false;
  emit('close-session');
};

const remotePointFromEvent = (event: MouseEvent): RemotePoint | null => {
  const image = event.currentTarget as HTMLImageElement;
  const rect = image.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const remoteWidth = image.naturalWidth || 1280;
  const remoteHeight = image.naturalHeight || 800;
  return {
    x: ((event.clientX - rect.left) / rect.width) * remoteWidth,
    y: ((event.clientY - rect.top) / rect.height) * remoteHeight,
  };
};

const sendRemoteClick = (event: MouseEvent) => {
  const point = remotePointFromEvent(event);
  if (!point) return;
  viewportRef.value?.focus({ preventScroll: true });
  if (!send({
    type: 'mouse_click',
    ...point,
  })) {
    errorMessage.value = '浏览器连接已断开，请等待重新连接后再操作';
    return;
  }
  remoteFocusMessage.value = '已聚焦远程页面，键盘输入将发送到当前焦点';
};

const handleImageClick = (event: MouseEvent) => {
  if (suppressNextClick.value) {
    suppressNextClick.value = false;
    return;
  }
  pauseForInteraction();
  sendRemoteClick(event);
  finishInteraction();
};

const suppressNativeClick = () => {
  suppressNextClick.value = true;
  if (typeof window !== 'undefined') {
    window.setTimeout(() => {
      suppressNextClick.value = false;
    }, 0);
  }
};

const releasePointerCapture = (event: PointerEvent) => {
  const image = event.currentTarget as HTMLImageElement;
  if (image.hasPointerCapture?.(event.pointerId)) {
    image.releasePointerCapture(event.pointerId);
  }
};

const handleImagePointerDown = (event: PointerEvent) => {
  if (event.pointerType === 'mouse' && event.button !== 0) return;
  const point = remotePointFromEvent(event);
  if (!point) return;
  event.preventDefault();
  pauseForInteraction();
  const image = event.currentTarget as HTMLImageElement;
  image.setPointerCapture?.(event.pointerId);
  pointerDownPoint.value = point;
  lastPointerPoint.value = point;
  pointerDragging.value = false;
  lastPointerMoveAt = 0;
};

const handleImagePointerMove = (event: PointerEvent) => {
  const start = pointerDownPoint.value;
  const point = remotePointFromEvent(event);
  if (!start || !point) return;
  lastPointerPoint.value = point;
  const distance = Math.hypot(point.x - start.x, point.y - start.y);
  if (!pointerDragging.value && distance < 3) return;
  event.preventDefault();
  if (!pointerDragging.value) {
    pointerDragging.value = true;
    remoteFocusMessage.value = '正在人工拖拽远程页面';
    send({ type: 'mouse_down', ...start });
  }
  const now = Date.now();
  if (now - lastPointerMoveAt < 16) return;
  lastPointerMoveAt = now;
  send({ type: 'mouse_move', ...point });
};

const handleImagePointerUp = (event: PointerEvent) => {
  const start = pointerDownPoint.value;
  const point = remotePointFromEvent(event) || lastPointerPoint.value;
  if (!start || !point) return;
  event.preventDefault();
  suppressNativeClick();
  if (pointerDragging.value) {
    send({ type: 'mouse_move', ...point });
    send({ type: 'mouse_up', ...point });
    remoteFocusMessage.value = '人工拖拽已发送到远程页面';
  } else {
    sendRemoteClick(event);
  }
  finishInteraction();
  releasePointerCapture(event);
  pointerDownPoint.value = null;
  lastPointerPoint.value = null;
  pointerDragging.value = false;
};

const handleImagePointerCancel = (event: PointerEvent) => {
  if (!pointerDownPoint.value) return;
  event.preventDefault();
  suppressNativeClick();
  if (pointerDragging.value) {
    const point = lastPointerPoint.value || pointerDownPoint.value;
    send({ type: 'mouse_up', ...point });
  }
  finishInteraction();
  releasePointerCapture(event);
  pointerDownPoint.value = null;
  lastPointerPoint.value = null;
  pointerDragging.value = false;
};

const handleKeydown = (event: KeyboardEvent) => {
  if (event.isComposing) return;
  event.preventDefault();
  pauseForInteraction();
  const modifiers = [
    event.ctrlKey ? 'Control' : '',
    event.altKey ? 'Alt' : '',
    event.shiftKey ? 'Shift' : '',
    event.metaKey ? 'Meta' : '',
  ].filter(Boolean);
  send({ type: 'key', key: [...modifiers, event.key].join('+') });
  scheduleInteractionFinish();
};

const handleWheel = (event: WheelEvent) => {
  pauseForInteraction();
  send({ type: 'scroll', delta_y: event.deltaY });
  scheduleInteractionFinish();
};

const sendText = () => {
  if (!manualText.value) return;
  if (!showManualInput.value) {
    remoteFocusMessage.value = '尚未点击远程输入区域，请先点击截图中的搜索框';
    return;
  }
  pauseForInteraction();
  send({ type: 'text', text: manualText.value });
  remoteFocusMessage.value = '文字已发送到远程页面';
  manualText.value = '';
  finishInteraction();
};

const normalizeNavigationUrl = (raw: string) => {
  const value = raw.trim();
  if (!value) return '';
  if (/^https?:\/\//i.test(value)) return value;
  if (value.startsWith('//')) return `https:${value}`;
  if (/^[a-z][a-z\d+.-]*:/i.test(value)) return value;
  return `https://${value}`;
};

const navigate = () => {
  const value = normalizeNavigationUrl(address.value);
  if (!value) return;
  address.value = value;
  pauseForInteraction();
  showManualInput.value = false;
  manualText.value = '';
  remoteFocusMessage.value = '页面导航中，请等待加载后重新点击输入区域';
  send({ type: 'navigate', url: value });
  finishInteraction();
};

watch(
  () => [props.visible, props.sessionId, props.viewerToken] as const,
  () => void connect(),
  { immediate: true },
);

watch(
  () => props.visible,
  (visible) => {
    showCloseSessionConfirm.value = false;
    showManualInput.value = false;
    manualText.value = '';
    controlOwner.value = 'ai';
    controlReason.value = null;
    captchaDetected.value = false;
    interactionInProgress.value = false;
    autoRefreshPaused.value = false;
    if (visible && !isMobile.value) pinned.value = true;
  },
);

watch(() => props.approvalMode,
  (mode, previous) => {
    if (mode === 'guarded' && previous !== 'guarded') {
      showSafetyNotice.value = true;
    }
  },
);

watch(() => props.refreshSignal, () => {
  if (!props.visible || !connected.value) return;
  if (controlOwner.value === 'human' || autoRefreshPaused.value || captchaDetected.value) return;
  requestSnapshot();
});

onMounted(() => {
  loadCustomWidth();
  mobileMq = window.matchMedia('(max-width: 639px)');
  syncMobile();
  mobileMq.addEventListener?.('change', syncMobile);
  window.addEventListener('resize', syncMobile);
});

onUnmounted(() => {
  stopResize();
  closeSocket();
  mobileMq?.removeEventListener?.('change', syncMobile);
  window.removeEventListener('resize', syncMobile);
});
</script>
