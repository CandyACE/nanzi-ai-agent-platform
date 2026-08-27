import { onUnmounted, ref } from "vue";

export interface ConversationRunStatus {
  active: boolean;
  trace_id?: string | null;
  ttl_seconds?: number | null;
}

export type ConversationRunStatusFetcher = (
  conversationId: string,
) => Promise<ConversationRunStatus | { data?: ConversationRunStatus | { data?: ConversationRunStatus } }>;

const EMPTY_STATUS: ConversationRunStatus = {
  active: false,
  trace_id: null,
  ttl_seconds: null,
};

const normalizeStatus = (
  response: ConversationRunStatus | { data?: ConversationRunStatus | { data?: ConversationRunStatus } },
): ConversationRunStatus => {
  const first = (response as { data?: unknown })?.data ?? response;
  const raw = ((first as { data?: unknown })?.data ?? first) as Partial<ConversationRunStatus> | null | undefined;
  return {
    active: raw?.active === true,
    trace_id: typeof raw?.trace_id === "string" ? raw.trace_id : null,
    ttl_seconds: typeof raw?.ttl_seconds === "number" ? raw.ttl_seconds : null,
  };
};

export function createConversationRunStatusController(
  fetchStatus: ConversationRunStatusFetcher,
  pollIntervalMs = 1500,
) {
  const remoteRunActive = ref(false);
  const status = ref<ConversationRunStatus>({ ...EMPTY_STATUS });
  let timer: ReturnType<typeof setTimeout> | null = null;
  let requestSequence = 0;
  let currentConversationId = "";

  const stopPolling = () => {
    requestSequence += 1;
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  };

  const scheduleNextPoll = (conversationId: string) => {
    if (timer || !remoteRunActive.value || conversationId !== currentConversationId) return;
    timer = setTimeout(() => {
      timer = null;
      void refresh(conversationId);
    }, pollIntervalMs);
  };

  const refresh = async (conversationId: string): Promise<boolean> => {
    const normalizedConversationId = String(conversationId || "").trim();
    currentConversationId = normalizedConversationId;
    const sequence = ++requestSequence;
    if (!normalizedConversationId) {
      stopPolling();
      remoteRunActive.value = false;
      status.value = { ...EMPTY_STATUS };
      return false;
    }

    try {
      const nextStatus = normalizeStatus(await fetchStatus(normalizedConversationId));
      if (sequence !== requestSequence || normalizedConversationId !== currentConversationId) {
        return remoteRunActive.value;
      }
      status.value = nextStatus;
      remoteRunActive.value = nextStatus.active;
      if (nextStatus.active) scheduleNextPoll(normalizedConversationId);
      else stopPolling();
      return nextStatus.active;
    } catch {
      if (sequence === requestSequence && normalizedConversationId === currentConversationId) {
        remoteRunActive.value = false;
        status.value = { ...EMPTY_STATUS };
        stopPolling();
      }
      return false;
    }
  };

  const startPolling = (conversationId: string) => {
    stopPolling();
    void refresh(conversationId);
  };

  const isPolling = () => timer !== null;

  return {
    remoteRunActive,
    status,
    refresh,
    startPolling,
    stopPolling,
    isPolling,
  };
}

export function useConversationRunStatus(fetchStatus: ConversationRunStatusFetcher) {
  const controller = createConversationRunStatusController(fetchStatus);
  onUnmounted(controller.stopPolling);
  return controller;
}
