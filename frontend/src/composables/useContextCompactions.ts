import { computed, ref } from "vue";
import { agentApi, type ContextCompactionRecord } from "@/api/agent";

export interface RefreshContextCompactionsOptions {
  conversationId?: string | null;
  headers?: Record<string, string>;
}

/**
 * 读取当前会话的上下文压缩记录。
 *
 * 压缩记录是辅助观测数据，和消息流、上下文使用量相互隔离；请求切换会话
 * 时通过 request id 丢弃旧响应，避免快速切换把上一会话的次数带到当前会话。
 */
export function useContextCompactions() {
  const contextCompactions = ref<ContextCompactionRecord[]>([]);
  const contextCompactionsLoading = ref(false);
  const contextCompactionsError = ref(false);
  const contextCompactionsLoadedFor = ref("");
  let latestRequestId = 0;

  const contextCompactionCount = computed(() =>
    contextCompactions.value.filter(
      (record) =>
        record.event_type === "context_summarized"
        || record.event_type === "context_compression",
    ).length,
  );

  const refreshContextCompactions = async (
    options: RefreshContextCompactionsOptions = {},
    force = false,
  ) => {
    const conversationId = String(options.conversationId || "").trim();
    const requestId = ++latestRequestId;

    if (!conversationId) {
      contextCompactions.value = [];
      contextCompactionsLoadedFor.value = "";
      contextCompactionsError.value = false;
      contextCompactionsLoading.value = false;
      return;
    }

    if (
      !force
      && contextCompactionsLoadedFor.value === conversationId
      && !contextCompactionsError.value
    ) {
      return;
    }

    contextCompactionsLoading.value = true;
    contextCompactionsError.value = false;
    try {
      const response = await agentApi.getContextCompactions(conversationId, {
        headers: options.headers,
      });
      if (requestId !== latestRequestId) return;
      const records = response.data?.data?.records;
      contextCompactions.value = Array.isArray(records) ? records : [];
      contextCompactionsLoadedFor.value = conversationId;
    } catch (error) {
      if (requestId !== latestRequestId) return;
      console.warn("Failed to fetch context compactions", error);
      contextCompactions.value = [];
      contextCompactionsLoadedFor.value = "";
      contextCompactionsError.value = true;
    } finally {
      if (requestId === latestRequestId) {
        contextCompactionsLoading.value = false;
      }
    }
  };

  return {
    contextCompactions,
    contextCompactionCount,
    contextCompactionsLoading,
    contextCompactionsError,
    refreshContextCompactions,
  };
}
