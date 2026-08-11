/** Business data confirmation card helpers (not tool-execution HITL). */

export type BusinessConfirmationValueType = "string" | "number" | "boolean" | "text";

export interface BusinessConfirmationField {
  key: string;
  label: string;
  value: unknown;
  editable?: boolean;
  value_type?: BusinessConfirmationValueType;
}

export interface BusinessConfirmationState {
  confirmation_id: string;
  tool_call_id?: string;
  title: string;
  summary?: string;
  fields: BusinessConfirmationField[];
  confirm_label: string;
  cancel_label: string;
  risk_note?: string;
  status: "pending" | "submitted" | "stale";
  decision?: "confirmed" | "cancelled";
}

export const BUSINESS_CONFIRMATION_MESSAGE_PREFIX = "【业务确认】";
export const BUSINESS_CONFIRMATION_CANCEL_MARKER = `${BUSINESS_CONFIRMATION_MESSAGE_PREFIX}用户已取消`;

export function isBusinessConfirmationCancelMessage(content: string | undefined | null): boolean {
  return String(content || "").includes(BUSINESS_CONFIRMATION_CANCEL_MARKER);
}

export function shouldSuppressBusinessConfirmation(
  messages?: Array<{ role?: string; content?: string }>,
): boolean {
  if (!messages?.length) return false;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i];
    const role = String(msg?.role || "").toLowerCase();
    if (role !== "user" && role !== "human") continue;
    return isBusinessConfirmationCancelMessage(msg?.content);
  }
  return false;
}

function asFields(raw: unknown): BusinessConfirmationField[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
    .map((item) => ({
      key: String(item.key || "").trim(),
      label: String(item.label || item.key || "字段").trim(),
      value: item.value ?? "",
      editable: item.editable !== false,
      value_type: (item.value_type as BusinessConfirmationValueType) || "string",
    }))
    .filter((item) => item.key || item.label);
}

export function parseBusinessConfirmationEvent(
  data: Record<string, unknown>,
): BusinessConfirmationState | null {
  if (String(data.type || "") !== "business_confirmation") return null;
  const confirmationId = String(data.confirmation_id || "").trim();
  const fields = asFields(data.fields);
  if (!confirmationId || fields.length === 0) return null;
  return {
    confirmation_id: confirmationId,
    tool_call_id: data.tool_call_id ? String(data.tool_call_id) : undefined,
    title: String(data.title || "请确认以下信息"),
    summary: String(data.summary || ""),
    fields,
    confirm_label: String(data.confirm_label || "确定"),
    cancel_label: String(data.cancel_label || "取消"),
    risk_note: String(data.risk_note || ""),
    status: "pending",
  };
}

export function formatBusinessConfirmationSnapshot(
  fields: BusinessConfirmationField[],
): string {
  return fields
    .map((field) => {
      const label = field.label || field.key || "字段";
      const value =
        field.value === null || field.value === undefined ? "" : String(field.value);
      if (field.key) return `- ${label} (${field.key}): ${value}`;
      return `- ${label}: ${value}`;
    })
    .join("\n");
}

export function buildBusinessConfirmationUserMessage(
  confirmed: boolean,
  confirmationId: string,
  fields: BusinessConfirmationField[],
): string {
  const snapshot = formatBusinessConfirmationSnapshot(fields);
  const cid = confirmationId.trim() || "unknown";
  if (confirmed) {
    return [
      `${BUSINESS_CONFIRMATION_MESSAGE_PREFIX}用户已确定`,
      `confirmation_id: ${cid}`,
      "请根据以下已确认字段继续执行（如需写入请调用相应工具）：",
      snapshot,
    ].join("\n");
  }
  return [
    `${BUSINESS_CONFIRMATION_MESSAGE_PREFIX}用户已取消`,
    `confirmation_id: ${cid}`,
    "请立即终止本次录入/变更：不要调用写入类工具；禁止再次调用 request_user_confirmation（不要重新弹确认卡）。只用文字确认已取消，并询问用户是否修改后重试或放弃。仅当用户随后明确提供新的/修改后的数据并要求继续时，才可再次请求确认。",
    "当时字段快照：",
    snapshot,
  ].join("\n");
}

export function markOtherBusinessConfirmationsStale<
  T extends { businessConfirmation?: BusinessConfirmationState },
>(messages: T[], activeConfirmationId: string): void {
  for (const msg of messages) {
    const card = msg.businessConfirmation;
    if (!card || card.status !== "pending") continue;
    if (card.confirmation_id === activeConfirmationId) continue;
    card.status = "stale";
  }
}
