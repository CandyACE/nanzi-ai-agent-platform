/** Helpers for the AI-initiated question interaction. */

export interface UserQuestionOption {
  id: string;
  label: string;
  description?: string;
}

export interface UserQuestionState {
  question_id: string;
  tool_call_id?: string;
  question: string;
  options: UserQuestionOption[];
  is_multi_select: boolean;
  allow_custom_input: boolean;
  context?: string;
  status: "pending" | "submitted" | "cancelled" | "stale";
  selected_option_ids?: string[];
  custom_input?: string;
}

export const USER_QUESTION_MESSAGE_PREFIX = "【用户回答】";

function normalizeOptions(raw: unknown): UserQuestionOption[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
    .map((item) => ({
      id: String(item.id || "").trim(),
      label: String(item.label || item.id || "选项").trim(),
      description: item.description ? String(item.description) : undefined,
    }))
    .filter((item) => item.id && item.label);
}

export function parseUserQuestionEvent(
  data: Record<string, unknown>,
): UserQuestionState | null {
  if (String(data.type || "") !== "user_question") return null;
  const questionId = String(data.question_id || "").trim();
  const question = String(data.question || "").trim();
  const options = normalizeOptions(data.options);
  if (!questionId || !question || options.length < 2) return null;
  const ids = new Set<string>();
  if (options.some((option) => ids.has(option.id) || (ids.add(option.id), false))) return null;
  return {
    question_id: questionId,
    tool_call_id: data.tool_call_id ? String(data.tool_call_id) : undefined,
    question,
    options,
    is_multi_select: Boolean(data.is_multi_select),
    allow_custom_input: Boolean(data.allow_custom_input),
    context: data.context ? String(data.context) : undefined,
    status: "pending",
  };
}

export function buildUserQuestionUserMessage(
  questionId: string,
  selectedOptionIds: string[],
  customInput = "",
  cancelled = false,
): string {
  const lines = [
    USER_QUESTION_MESSAGE_PREFIX,
    "interaction_type: question",
    `question_id: ${questionId.trim() || "unknown"}`,
    `selected_option_ids: ${JSON.stringify(selectedOptionIds)}`,
    `custom_input: ${customInput.trim()}`,
  ];
  if (cancelled) {
    lines.push("cancelled: true", "用户取消了本次提问，请停止当前任务，不要再次询问同一个问题。");
  } else {
    lines.push("请根据以上用户回答继续处理原问题。");
  }
  return lines.join("\n");
}

export function markOtherUserQuestionsStale<
  T extends { userQuestion?: UserQuestionState },
>(messages: T[], activeQuestionId: string): void {
  for (const message of messages) {
    const question = message.userQuestion;
    if (!question || question.status !== "pending") continue;
    if (question.question_id === activeQuestionId) continue;
    question.status = "stale";
  }
}
