import axios from './axios'

export interface CancelConversationRunOptions {
  traceId?: string
  headers?: Record<string, string>
}

/**
 * Cancel the current conversation generation on the backend, then the caller
 * should abort the SSE fetch. Failures are logged only.
 */
export async function cancelConversationRun(
  conversationId: string,
  options?: CancelConversationRunOptions
): Promise<void> {
  const cid = (conversationId || '').trim()
  if (!cid) return

  try {
    await axios.post(
      '/api/v1/chat/cancel',
      {
        conversation_id: cid,
        trace_id: options?.traceId || undefined,
      },
      options?.headers ? { headers: options.headers } : undefined
    )
  } catch (e) {
    console.warn('[Chat] cancel conversation run failed', cid, e)
  }
}
