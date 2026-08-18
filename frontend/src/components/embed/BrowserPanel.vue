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
            {{ connected ? '已连接，可人工接管' : '正在连接…' }}
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
                @click="emit('close-session')"
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
              placeholder="输入 http(s) 地址后回车"
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
            <span class="shrink-0 text-sky-600 dark:text-sky-300">每 2 秒自动刷新</span>
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
            <div v-if="screenshotUrl" class="relative">
              <img
                :key="snapshot.snapshot_id"
                :src="screenshotUrl"
                alt="远程浏览器画面"
                class="block w-full cursor-crosshair rounded border border-gray-200 bg-white shadow-sm dark:border-gray-700"
                @click="handleImageClick"
              />
              <span
                v-if="lastClickStyle"
                :style="lastClickStyle"
                class="pointer-events-none absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-blue-600 bg-blue-400/30 shadow-[0_0_0_3px_rgba(255,255,255,0.8)] dark:border-blue-300 dark:bg-blue-400/30"
                aria-hidden="true"
              />
            </div>
            <div v-else class="flex h-full min-h-56 items-center justify-center text-xs text-gray-400">等待浏览器画面…</div>
          </div>

          <footer class="shrink-0 border-t border-gray-200 bg-white p-2 dark:border-gray-700 dark:bg-gray-900">
            <div class="mb-1 flex items-center justify-between text-[10px] text-gray-400">
              <span class="truncate">{{ snapshot?.title || '未加载页面' }}</span>
              <button class="shrink-0 text-blue-600 hover:underline dark:text-blue-300" @click="requestSnapshot">刷新画面</button>
            </div>
            <div class="flex gap-2">
              <input
                v-model="manualText"
                type="text"
                autocomplete="off"
                class="min-w-0 flex-1 rounded-md border border-gray-200 bg-gray-50 px-2 py-1.5 text-xs outline-none focus:border-blue-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                placeholder="人工输入（回车发送到远程页面）"
                @keyup.enter="sendText"
              />
              <button class="rounded-md border border-gray-200 px-2.5 py-1.5 text-[10px] font-bold text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800" @click="sendText">输入</button>
            </div>
            <div class="mt-1 text-[10px] leading-relaxed text-gray-400">可直接点击截图、滚轮、输入文字或按键；智能体与人工操作共享此浏览器会话。</div>
          </footer>
        </section>
      </aside>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

type ApprovalMode = 'guarded' | 'autopilot';
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
  url: string;
  title: string;
  screenshot_ref?: string | null;
  elements: BrowserElement[];
};

const props = defineProps<{
  visible: boolean;
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

const socket = ref<WebSocket | null>(null);
const connected = ref(false);
const snapshot = ref<BrowserSnapshot | null>(null);
const errorMessage = ref('');
const address = ref('');
const manualText = ref('');
const remoteFocusMessage = ref('请先点击截图中的输入框，再使用下方人工输入');
const lastClick = ref<{ x: number; y: number } | null>(null);
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
const lastClickStyle = computed<Record<string, string> | null>(() => {
  if (!lastClick.value) return null;
  return {
    left: `${(lastClick.value.x / 1280) * 100}%`,
    top: `${(lastClick.value.y / 800) * 100}%`,
  };
});
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let pollTimer: ReturnType<typeof setInterval> | null = null;

const closeSocket = () => {
  connected.value = false;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
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
  if (!props.visible || !props.sessionId || !props.viewerToken || typeof window === 'undefined') return;
  await nextTick();
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${scheme}//${window.location.host}/api/v1/chat/browser/sessions/${encodeURIComponent(props.sessionId)}/viewer`;
  const client = new WebSocket(url, [`browser-viewer.${props.viewerToken}`]);
  socket.value = client;
  client.onopen = () => {
    connected.value = true;
    client.send(JSON.stringify({ type: 'snapshot' }));
    pollTimer = setInterval(requestSnapshot, 2000);
  };
  client.onmessage = (event) => {
    let payload: { type?: string; snapshot?: BrowserSnapshot; message?: string };
    try {
      payload = JSON.parse(event.data) as { type?: string; snapshot?: BrowserSnapshot; message?: string };
    } catch {
      errorMessage.value = '浏览器返回了无法识别的消息';
      return;
    }
    if (payload.type === 'snapshot' && payload.snapshot) {
      const previousUrl = snapshot.value?.url;
      snapshot.value = payload.snapshot;
      address.value = payload.snapshot.url || address.value;
      if (previousUrl && previousUrl !== payload.snapshot.url) {
        lastClick.value = null;
        remoteFocusMessage.value = '页面已变化，请重新点击要输入的区域';
      }
    } else if (payload.type === 'error') {
      errorMessage.value = payload.message || '浏览器操作失败';
    }
  };
  client.onerror = () => {
    errorMessage.value = '浏览器连接失败，请稍后重试';
  };
  client.onclose = () => {
    connected.value = false;
    if (props.visible && socket.value === client) {
      reconnectTimer = setTimeout(() => void connect(), 1500);
    }
  };
};

const send = (payload: Record<string, unknown>) => {
  if (socket.value?.readyState === WebSocket.OPEN) {
    socket.value.send(JSON.stringify(payload));
  }
};

const requestSnapshot = () => send({ type: 'snapshot' });

const handleImageClick = (event: MouseEvent) => {
  const image = event.currentTarget as HTMLImageElement;
  const rect = image.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const x = ((event.clientX - rect.left) / rect.width) * 1280;
  const y = ((event.clientY - rect.top) / rect.height) * 800;
  lastClick.value = { x, y };
  remoteFocusMessage.value = '已聚焦远程页面，键盘输入将发送到当前焦点';
  viewportRef.value?.focus({ preventScroll: true });
  send({
    type: 'mouse_click',
    x,
    y,
  });
};

const handleKeydown = (event: KeyboardEvent) => {
  if (event.isComposing) return;
  event.preventDefault();
  send({ type: 'key', key: event.key });
};

const handleWheel = (event: WheelEvent) => {
  send({ type: 'scroll', delta_y: event.deltaY });
};

const sendText = () => {
  if (!manualText.value) return;
  if (!lastClick.value) {
    remoteFocusMessage.value = '尚未点击远程输入区域，请先点击截图中的搜索框';
    return;
  }
  send({ type: 'text', text: manualText.value });
  remoteFocusMessage.value = '文字已发送到远程页面';
  manualText.value = '';
};

const navigate = () => {
  const value = address.value.trim();
  if (!value) return;
  lastClick.value = null;
  remoteFocusMessage.value = '页面导航中，请等待加载后重新点击输入区域';
  send({ type: 'navigate', url: value });
};

watch(
  () => [props.visible, props.sessionId, props.viewerToken] as const,
  () => void connect(),
  { immediate: true },
);

watch(
  () => props.visible,
  (visible) => {
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
