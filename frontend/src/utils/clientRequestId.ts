/** 为一次用户发送意图生成稳定、短小且不依赖后端的请求 ID。 */
export function createClientRequestId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    // 旧浏览器或受限 iframe 环境没有 crypto.randomUUID 时走回退值。
  }
  return `chat-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}
