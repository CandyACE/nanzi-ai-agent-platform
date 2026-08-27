import { ref } from 'vue';

export interface ChatSendGate {
  locked: ReturnType<typeof ref<boolean>>;
  runExclusive<T>(task: () => Promise<T> | T): Promise<T | undefined>;
}

/**
 * 给所有发送入口提供同步提交门禁。
 *
 * 这里不复用 isProcessing：发送前的异步准备阶段还没有可取消的模型任务，
 * 不能因为门禁状态把“停止生成”误显示给用户。
 */
export function createChatSendGate(): ChatSendGate {
  const locked = ref(false);

  const runExclusive = async <T>(task: () => Promise<T> | T): Promise<T | undefined> => {
    if (locked.value) return undefined;
    locked.value = true;
    try {
      return await task();
    } finally {
      locked.value = false;
    }
  };

  return { locked, runExclusive };
}
