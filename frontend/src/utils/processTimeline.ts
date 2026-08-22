import type { SubagentTraceMeta } from "./subagentTrace";

export type ProcessTimelineStatus = "pending" | "success" | "error" | "warning";
export type ToolResolutionStatus = "disabled" | "missing" | "filtered";
export type ProcessTimelineTodoStatus = "pending" | "in_progress" | "completed";

export type ProcessTimelineTextItem = {
  kind: "text";
  id: string;
  textKind: "narration" | "reasoning";
  content: string;
  pending: boolean;
  started_at?: number | null;
  execution_time_ms?: number | null;
  children?: ProcessTimelineLogItem[];
  childrenExpanded?: boolean;
  /** 深度思考正文是否展开；未设置时：进行中展开，结束后折叠。 */
  contentExpanded?: boolean;
  /** Parallel expert streams key pending narration by agent name. */
  sourceId?: string;
  sourceLabel?: string;
};

export type ProcessTimelineLogItem = {
  kind: "log";
  id: string | number;
  title: string;
  details: string;
  status: ProcessTimelineStatus;
  category?: string;
  tool_name?: string;
  resolution_status?: ToolResolutionStatus;
  execution_time_ms?: number | null;
  started_at?: number | null;
  subagent?: SubagentTraceMeta;
  isExpanded?: boolean;
  children?: ProcessTimelineLogItem[];
  childrenExpanded?: boolean;
};

export type ProcessTimelineTodo = {
  content: string;
  status: ProcessTimelineTodoStatus;
};

export type ProcessTimelineTodoItem = {
  kind: "todo";
  id: string;
  title: string;
  todos: ProcessTimelineTodo[];
  counts: Record<ProcessTimelineTodoStatus, number>;
};

export type ProcessTimelineItem = ProcessTimelineTextItem | ProcessTimelineLogItem | ProcessTimelineTodoItem;

export function timelineHasPending(items: ProcessTimelineItem[] | undefined): boolean {
  return (items || []).some((item) => {
    if (item.kind === "log") {
      if (item.status === "pending") return true;
      return (item.children || []).some((child) => child.status === "pending");
    }
    if (item.kind === "todo") {
      return item.todos.some((todo) => todo.status === "pending" || todo.status === "in_progress");
    }
    if (item.pending) return true;
    return (item.children || []).some((child) => {
      if (child.status === "pending") return true;
      return (child.children || []).some((grandChild) => grandChild.status === "pending");
    });
  });
}

/**
 * Return the compact step summary shown in the collapsed timeline header.
 * Prefer the newest pending tool/narration so the header reflects what is
 * happening now instead of only showing the total step count.
 */
export function resolveTimelineCurrentStep(
  items: ProcessTimelineItem[] | undefined,
  active: boolean,
): string {
  if (!active) return "";

  for (const item of [...(items || [])].reverse()) {
    if (item.kind === "log") {
      const pendingSub = [...(item.children || [])].reverse().find((child) => child.status === "pending");
      if (pendingSub) return `${pendingSub.title} · 进行中`;
      if (item.status === "pending") return `${item.title} · 进行中`;
    }
    if (item.kind === "todo") {
      const current = item.todos.find((todo) => todo.status === "in_progress")
        || item.todos.find((todo) => todo.status === "pending");
      if (current) return `${current.content} · 进行中`;
    }
    if (item.kind === "text" && item.pending && item.content.trim()) {
      const pendingChild = [...(item.children || [])].reverse().find((child) => child.status === "pending");
      if (pendingChild) {
        const pendingSub = [...(pendingChild.children || [])].reverse().find((sub) => sub.status === "pending");
        if (pendingSub) return `${pendingSub.title} · 进行中`;
        return `${pendingChild.title} · 进行中`;
      }
      return item.content.trim();
    }
    if (item.kind === "text") {
      const pendingChild = [...(item.children || [])].reverse().find((child) => child.status === "pending");
      if (pendingChild) {
        const pendingSub = [...(pendingChild.children || [])].reverse().find((sub) => sub.status === "pending");
        if (pendingSub) return `${pendingSub.title} · 进行中`;
        return `${pendingChild.title} · 进行中`;
      }
    }
  }
  return "";
}

export type ProcessTimelineTarget = {
  processTimeline?: ProcessTimelineItem[];
};

function normalizeTodoItems(rawTodos: unknown): ProcessTimelineTodo[] | undefined {
  if (!Array.isArray(rawTodos)) return undefined;
  const seen = new Set<string>();
  const todos: ProcessTimelineTodo[] = [];
  for (const rawTodo of rawTodos) {
    if (!rawTodo || typeof rawTodo !== "object") return undefined;
    const content = String((rawTodo as { content?: unknown }).content || "").trim();
    const status = (rawTodo as { status?: unknown }).status;
    if (!content || (status !== "pending" && status !== "in_progress" && status !== "completed")) {
      return undefined;
    }
    if (seen.has(content)) return undefined;
    seen.add(content);
    todos.push({ content, status });
  }
  return todos;
}

function todoCounts(todos: ProcessTimelineTodo[]): Record<ProcessTimelineTodoStatus, number> {
  return {
    pending: todos.filter((todo) => todo.status === "pending").length,
    in_progress: todos.filter((todo) => todo.status === "in_progress").length,
    completed: todos.filter((todo) => todo.status === "completed").length,
  };
}

/** Replace the current main-agent checklist while keeping it as a timeline sibling. */
export function upsertTimelineTodo(
  target: ProcessTimelineTarget,
  data: { todos: unknown; title?: unknown },
): void {
  const todos = normalizeTodoItems(data.todos);
  if (!todos) return;
  if (!target.processTimeline) target.processTimeline = [];
  const items = target.processTimeline;
  const indexes = items
    .map((item, index) => item.kind === "todo" ? index : -1)
    .filter((index) => index >= 0);
  if (!todos.length) {
    for (const index of indexes.reverse()) items.splice(index, 1);
    return;
  }

  const todo: ProcessTimelineTodoItem = {
    kind: "todo",
    id: "todo_current",
    title: String(data.title || "任务清单"),
    todos,
    counts: todoCounts(todos),
  };
  if (indexes.length) {
    const firstIndex = indexes[0];
    if (firstIndex === undefined) return;
    items[firstIndex] = todo;
    for (const index of indexes.slice(1).reverse()) items.splice(index, 1);
  } else {
    items.push(todo);
  }
  target.processTimeline = [...items];
}

let textSequence = 0;

function nextTextId(kind: ProcessTimelineTextItem["textKind"]): string {
  textSequence += 1;
  return `${kind}_${Date.now()}_${textSequence}`;
}

function lastTextItem(
  target: ProcessTimelineTarget,
  textKind: ProcessTimelineTextItem["textKind"],
): ProcessTimelineTextItem | undefined {
  const items = target.processTimeline || [];
  const item = items[items.length - 1];
  return item?.kind === "text" && item.textKind === textKind ? item : undefined;
}

function lastPendingTextItem(
  target: ProcessTimelineTarget,
  textKind: ProcessTimelineTextItem["textKind"],
  sourceId?: string,
): ProcessTimelineTextItem | undefined {
  for (const item of [...(target.processTimeline || [])].reverse()) {
    if (item.kind !== "text" || item.textKind !== textKind || !item.pending) continue;
    if (sourceId) {
      if (item.sourceId === sourceId) return item;
      continue;
    }
    return item;
  }
  return undefined;
}

function hasVisibleText(text: string): boolean {
  return Boolean(String(text || "").replace(/[\s\u200b\u200c\u200d\ufeff]/g, ""));
}

/** Keep process narration readable without changing answer or tool details. */
export function normalizeProcessNarrationText(text: string, trimBoundary = false): string {
  let normalized = String(text || "")
    .replace(/\r\n?/g, "\n")
    .replace(/\n[ \t]*\n(?:[ \t]*\n)+/g, "\n\n");
  if (trimBoundary) {
    normalized = normalized
      .replace(/^[ \t]*\n+/, "")
      .replace(/\n+[ \t]*$/, "");
  }
  return normalized;
}

export function appendProcessNarrationText(existing: string, piece: string): string {
  const combined = normalizeProcessNarrationText(`${existing || ""}${piece || ""}`);
  return existing ? combined : combined.replace(/^[ \t]*\n+/, "");
}

function isToolLog(data: { title?: string; category?: string; id?: string | number }): boolean {
  const category = String(data.category || "").toLowerCase();
  if (category === "permission" || category === "external") return false;
  if (category === "tool" || category === "sql" || category === "agent" || category === "tool_resolution") return true;
  if (category) return false;
  const title = String(data.title || "").toLowerCase();
  if (
    title.includes("权限")
    || title.includes("permission")
    || title.includes("确认")
    || title.includes("外部执行")
  ) {
    return false;
  }
  const idStr = String(data.id || "").toLowerCase();
  if (idStr.startsWith("subagent_")) return true;
  return title.includes("工具") || title.includes("tool") || title.includes("子代理");
}

function findTimelineLog(
  items: ProcessTimelineItem[],
  id: string | number,
): ProcessTimelineLogItem | undefined {
  for (const item of items) {
    if (item.kind === "log") {
      if (item.id === id) return item;
      if (item.children?.length) {
        const found = findTimelineLogInLogs(item.children, id);
        if (found) return found;
      }
    } else if (item.kind === "text") {
      for (const child of item.children || []) {
        if (child.id === id) return child;
        if (child.children?.length) {
          const found = findTimelineLogInLogs(child.children, id);
          if (found) return found;
        }
      }
    }
  }
  return undefined;
}

function findTimelineLogInLogs(
  logs: ProcessTimelineLogItem[],
  id: string | number,
): ProcessTimelineLogItem | undefined {
  for (const log of logs) {
    if (log.id === id) return log;
    if (log.children?.length) {
      const found = findTimelineLogInLogs(log.children, id);
      if (found) return found;
    }
  }
  return undefined;
}

function findSubagentContainerLog(
  items: ProcessTimelineItem[],
  subagent: SubagentTraceMeta,
): ProcessTimelineLogItem | undefined {
  const targetRunId = subagent.run_id;
  const targetChildTraceId = subagent.child_trace_id;

  const matchContainer = (log: ProcessTimelineLogItem): boolean => {
    if (targetRunId && log.id === `subagent_${targetRunId}`) return true;
    if (targetRunId && log.subagent?.run_id === targetRunId && String(log.id).startsWith("subagent_")) return true;
    if (targetChildTraceId && log.subagent?.child_trace_id === targetChildTraceId && String(log.id).startsWith("subagent_")) return true;
    if (log.title.includes("sub_agent_call") && (!log.subagent || log.subagent.run_id === targetRunId)) return true;
    return false;
  };

  for (const item of items) {
    if (item.kind === "log") {
      if (matchContainer(item)) return item;
    } else if (item.kind === "text") {
      for (const child of item.children || []) {
        if (matchContainer(child)) return child;
      }
    }
  }
  return undefined;
}

export function appendTimelineNarrationDelta(
  target: ProcessTimelineTarget,
  piece: string,
  sourceId?: string,
): void {
  const text = String(piece || "");
  if (!text) return;
  if (!target.processTimeline) target.processTimeline = [];
  finishPendingReasoningItems(target);
  // Parallel agent streams can insert a log between two deltas belonging to
  // the same narration. Keep appending to the matching pending narration
  // instead of creating a second fragment that will be finalized independently.
  const current = lastPendingTextItem(target, "narration", sourceId);
  if (current) {
    current.content = appendProcessNarrationText(current.content, text);
    return;
  }
  if (!hasVisibleText(text)) return;
  target.processTimeline.push({
    kind: "text",
    id: nextTextId("narration"),
    textKind: "narration",
    content: appendProcessNarrationText("", text),
    pending: true,
    started_at: Date.now(),
    children: [],
    childrenExpanded: true,
    sourceId,
    sourceLabel: sourceId,
  });
}

export function commitTimelineNarration(
  target: ProcessTimelineTarget,
  piece = "",
  sourceId?: string,
): void {
  if (!target.processTimeline) target.processTimeline = [];
  const current = lastPendingTextItem(target, "narration", sourceId);
  const text = String(piece || "");
  if (current) {
    if (text) current.content = normalizeProcessNarrationText(text, true);
    current.pending = false;
    current.children ||= [];
    current.childrenExpanded ??= true;
    return;
  }
  if (text) {
    target.processTimeline.push({
      kind: "text",
      id: nextTextId("narration"),
      textKind: "narration",
      content: text,
      pending: false,
      children: [],
      childrenExpanded: true,
      sourceId,
      sourceLabel: sourceId,
    });
  }
}

export function promoteTimelineNarration(
  target: ProcessTimelineTarget,
  piece = "",
  sourceId?: string,
): void {
  const items = target.processTimeline || [];
  const current = lastPendingTextItem(target, "narration", sourceId);
  if (!current?.pending) return;
  const text = String(piece || "");
  if (!text) {
    const index = items.indexOf(current);
    if (index >= 0) items.splice(index, 1);
    return;
  }
  // 时间线内容经过 normalize（去首尾空白、\r\n→\n、折叠空行），promote 文本是
  // 后端原文；直接比较会在正文以换行开头或含 \r\n 时匹配失败，留下整段正文的
  // pending 条目，与正文气泡重复展示。两端归一化后再比较。
  const currentNormalized = normalizeProcessNarrationText(current.content, true);
  const pieceNormalized = normalizeProcessNarrationText(text, true);
  if (currentNormalized === pieceNormalized || currentNormalized.endsWith(pieceNormalized)) {
    const index = items.indexOf(current);
    if (index >= 0) items.splice(index, 1);
  }
}

/** Remove a narration candidate when the stream has begun emitting final text. */
export function discardPendingTimelineNarration(target: ProcessTimelineTarget): void {
  const items = target.processTimeline || [];
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const item = items[index];
    if (item?.kind === "text" && item.textKind === "narration" && item.pending) {
      items.splice(index, 1);
    }
  }
}

export function appendTimelineReasoningDelta(target: ProcessTimelineTarget, piece: string): void {
  const text = String(piece || "");
  if (!text) return;
  if (!target.processTimeline) target.processTimeline = [];
  const current = lastTextItem(target, "reasoning");
  if (current?.pending) {
    current.content += text;
    return;
  }
  target.processTimeline.push({
    kind: "text",
    id: nextTextId("reasoning"),
    textKind: "reasoning",
    content: text,
    pending: true,
    started_at: Date.now(),
  });
}

export function finishTimelineReasoning(target: ProcessTimelineTarget): void {
  finishPendingReasoningItems(target);
}

function finishPendingReasoningItems(target: ProcessTimelineTarget): void {
  const now = Date.now();
  for (const item of target.processTimeline || []) {
    if (item.kind !== "text" || item.textKind !== "reasoning" || !item.pending) continue;
    if (!item.execution_time_ms && item.started_at) {
      item.execution_time_ms = Math.max(1, now - item.started_at);
    }
    item.pending = false;
  }
}

export function isReasoningContentExpanded(item: ProcessTimelineTextItem): boolean {
  if (item.textKind !== "reasoning") return true;
  if (item.contentExpanded === true) return true;
  if (item.contentExpanded === false) return false;
  return item.pending;
}

export function upsertTimelineLog(
  target: ProcessTimelineTarget,
  data: {
    id: string | number;
    title?: string;
    details?: string;
    status?: ProcessTimelineStatus;
    category?: string;
    tool_name?: string;
    resolution_status?: ToolResolutionStatus;
    execution_time_ms?: number | null;
    started_at?: number | null;
    subagent?: SubagentTraceMeta;
  },
): void {
  if (!target.processTimeline) target.processTimeline = [];
  const existing = findTimelineLog(target.processTimeline, data.id);
  if (existing) {
    if (data.title !== undefined) existing.title = data.title;
    if (data.details !== undefined) existing.details = data.details;
    if (data.status !== undefined) existing.status = data.status;
    if (data.category !== undefined) existing.category = data.category;
    if (data.tool_name !== undefined) existing.tool_name = data.tool_name;
    if (data.resolution_status !== undefined) existing.resolution_status = data.resolution_status;
    if (data.execution_time_ms !== undefined) existing.execution_time_ms = data.execution_time_ms;
    if (data.started_at !== undefined) existing.started_at = data.started_at;
    if (data.subagent !== undefined) existing.subagent = data.subagent;
    return;
  }

  // Deduplicate sub_agent_call tool completion into existing subagent container if already present
  if (data.title && data.title.includes("sub_agent_call")) {
    const existingContainer = [...target.processTimeline].reverse().find((item) => {
      if (item.kind === "log" && String(item.id).startsWith("subagent_")) return true;
      if (item.kind === "text") {
        return (item.children || []).some((c) => String(c.id).startsWith("subagent_"));
      }
      return false;
    });
    if (existingContainer) {
      let containerLog: ProcessTimelineLogItem | undefined;
      if (existingContainer.kind === "log") {
        containerLog = existingContainer;
      } else if (existingContainer.kind === "text") {
        containerLog = (existingContainer.children || [])
          .find((c: ProcessTimelineLogItem) => String(c.id).startsWith("subagent_"));
      }
      if (containerLog) {
        if (data.execution_time_ms !== undefined) containerLog.execution_time_ms = data.execution_time_ms;
        if (data.status !== undefined) containerLog.status = data.status;
        if (data.details) containerLog.details = data.details;
        return;
      }
    }
  }

  const log: ProcessTimelineLogItem = {
    kind: "log",
    id: data.id,
    title: data.title || "处理步骤",
    details: data.details || "",
    status: data.status || "success",
    category: data.category,
    tool_name: data.tool_name,
    resolution_status: data.resolution_status,
    execution_time_ms: data.execution_time_ms,
    started_at: data.started_at,
    subagent: data.subagent,
    isExpanded: false,
    children: [],
    childrenExpanded: true,
  };

  // If this is an inner step of a subagent (subagent metadata present, but not the subagent container itself)
  const isSubagentContainer = String(data.id).startsWith("subagent_") || (data.title && data.title.includes("sub_agent_call"));
  if (data.subagent && !isSubagentContainer) {
    const subagentContainer = findSubagentContainerLog(target.processTimeline, data.subagent);
    if (subagentContainer) {
      subagentContainer.children ||= [];
      subagentContainer.children.push(log);
      subagentContainer.childrenExpanded ??= true;
      return;
    }
  }

  const parent = isToolLog(data)
    ? [...target.processTimeline].reverse().find(
      (item): item is ProcessTimelineTextItem =>
        item.kind === "text" && item.textKind === "narration" && !item.pending,
    )
    : undefined;
  if (parent) {
    parent.children ||= [];
    parent.children.push(log);
    parent.childrenExpanded ??= true;
    return;
  }
  target.processTimeline.push(log);
}

/**
 * Merge the authoritative event timeline with logs produced by legacy paths.
 * Some router/agent events already enter processTimeline while later tool
 * events still only update msg.logs; dropping the latter makes the card look
 * like it ends and then continues outside the card.
 */
export function mergeTimelineLogs(
  timeline: ProcessTimelineItem[] | undefined,
  logs: Array<{
    id: string | number;
    title: string;
    details: string;
    status: ProcessTimelineStatus;
    category?: string;
    tool_name?: string;
    resolution_status?: ToolResolutionStatus;
    execution_time_ms?: number | null;
    started_at?: number | null;
    subagent?: SubagentTraceMeta;
  }> | undefined,
): ProcessTimelineItem[] {
  const items = [...(timeline || [])];
  const indexes = new Map<string | number, number>();
  items.forEach((item, index) => {
    if (item.kind === "log") indexes.set(item.id, index);
    if (item.kind === "text") {
      for (const child of item.children || []) indexes.set(child.id, index);
    }
  });

  for (const log of logs || []) {
    const existingIndex = indexes.get(log.id);
    if (existingIndex !== undefined) {
      const existing = items[existingIndex];
      const nested = findTimelineLog(items, log.id);
      const targetLog = nested || (existing?.kind === "log" ? existing : undefined);
      if (targetLog) {
        targetLog.title = log.title || targetLog.title;
        targetLog.details = log.details ?? targetLog.details;
        targetLog.status = log.status || targetLog.status;
        targetLog.category = log.category ?? targetLog.category;
        targetLog.tool_name = log.tool_name ?? targetLog.tool_name;
        targetLog.resolution_status = log.resolution_status ?? targetLog.resolution_status;
        targetLog.execution_time_ms = log.execution_time_ms ?? targetLog.execution_time_ms;
        targetLog.started_at = log.started_at ?? targetLog.started_at;
        targetLog.subagent = log.subagent ?? targetLog.subagent;
      }
      continue;
    }
    upsertTimelineLog({ processTimeline: items }, log);
    indexes.set(log.id, items.length - 1);
  }
  return items;
}

export function buildLegacyProcessTimeline(input: {
  logs?: Array<{
    id: string | number;
    title: string;
    details: string;
    status: ProcessTimelineStatus;
    category?: string;
    tool_name?: string;
    resolution_status?: ToolResolutionStatus;
    execution_time_ms?: number | null;
    started_at?: number | null;
    subagent?: SubagentTraceMeta;
  }>;
  reasoningContent?: string;
  processNarration?: string;
  processNarrationPending?: string;
}): ProcessTimelineItem[] {
  const items: ProcessTimelineItem[] = [];
  // 历史消息没有事件序列，只能保留旧页面的兼容顺序：步骤日志在前，
  // 过程/思考文本在后。新消息会直接走 processTimeline，具备精确顺序。
  for (const log of input.logs || []) {
    items.push({ kind: "log", ...log, isExpanded: false, children: [], childrenExpanded: true });
  }
  if (input.processNarration) {
    items.push({
      kind: "text",
      id: "legacy_narration",
      textKind: "narration",
      content: input.processNarration,
      pending: false,
    });
  }
  if (input.processNarrationPending) {
    items.push({
      kind: "text",
      id: "legacy_narration_pending",
      textKind: "narration",
      content: input.processNarrationPending,
      pending: true,
    });
  }
  if (input.reasoningContent) {
    items.push({
      kind: "text",
      id: "legacy_reasoning",
      textKind: "reasoning",
      content: input.reasoningContent,
      pending: false,
    });
  }
  return items;
}

function reorganizeSubagentItems(items: ProcessTimelineItem[]): ProcessTimelineItem[] {
  const result: ProcessTimelineItem[] = [];

  const isContainer = (log: ProcessTimelineLogItem): boolean =>
    String(log.id).startsWith("subagent_") ||
    log.title.includes("调用子代理") ||
    log.title.includes("sub_agent_call");

  const isInnerSubagentStep = (log: ProcessTimelineLogItem): boolean =>
    !isContainer(log) && (Boolean(log.subagent) || log.title.startsWith("["));

  let activeContainer: ProcessTimelineLogItem | undefined = undefined;
  let activeNarration: ProcessTimelineTextItem | undefined = undefined;

  for (const item of items) {
    if (item.kind === "text") {
      if (item.children?.length) {
        const newChildren: ProcessTimelineLogItem[] = [];
        let subContainer: ProcessTimelineLogItem | undefined = undefined;
        const innerSteps: ProcessTimelineLogItem[] = [];

        for (const child of item.children) {
          if (isContainer(child)) {
            if (subContainer) {
              subContainer.execution_time_ms = child.execution_time_ms || subContainer.execution_time_ms;
              subContainer.status = child.status || subContainer.status;
              if (child.details) subContainer.details = child.details;
              if (child.title.includes("调用子代理") || child.subagent) subContainer.title = child.title;
              if (child.subagent) subContainer.subagent = child.subagent;
              for (const inner of child.children || []) innerSteps.push(inner);
            } else {
              subContainer = child;
              subContainer.children ||= [];
              for (const inner of child.children || []) innerSteps.push(inner);
            }
          } else if (isInnerSubagentStep(child)) {
            innerSteps.push(child);
          } else {
            newChildren.push(child);
          }
        }

        if (subContainer) {
          subContainer.children = [...(subContainer.children || []), ...innerSteps];
          subContainer.childrenExpanded = true;
          newChildren.push(subContainer);
          activeContainer = subContainer;
        } else if (innerSteps.length && activeContainer) {
          activeContainer.children ||= [];
          activeContainer.children.push(...innerSteps);
        }
        item.children = newChildren;
      }
      activeNarration = item;
      result.push(item);
      continue;
    }

    if (item.kind === "log" && isContainer(item)) {
      if (activeContainer) {
        activeContainer.execution_time_ms = item.execution_time_ms || activeContainer.execution_time_ms;
        activeContainer.status = item.status || activeContainer.status;
        if (item.details) activeContainer.details = item.details;
        if (item.title.includes("调用子代理") || item.subagent) activeContainer.title = item.title;
        if (item.subagent) activeContainer.subagent = item.subagent;
        for (const inner of item.children || []) activeContainer.children?.push(inner);
      } else if (activeNarration) {
        item.children ||= [];
        activeNarration.children ||= [];
        activeNarration.children.push(item);
        activeContainer = item;
      } else {
        item.children ||= [];
        result.push(item);
        activeContainer = item;
      }
      continue;
    }

    if (item.kind === "log" && isInnerSubagentStep(item)) {
      if (activeContainer) {
        activeContainer.children ||= [];
        activeContainer.children.push(item);
        continue;
      }
      if (activeNarration) {
        const c = activeNarration.children?.find(isContainer);
        if (c) {
          c.children ||= [];
          c.children.push(item);
          activeContainer = c;
          continue;
        }
      }
    }

    result.push(item);
  }

  return result;
}

export function hydrateHistoryProcessTimeline(
  stored: ProcessTimelineItem[] | undefined,
  reasoningContent?: string,
): ProcessTimelineItem[] {
  const mapLog = (log: ProcessTimelineLogItem): ProcessTimelineLogItem => ({
    ...log,
    isExpanded: false,
    childrenExpanded: true,
    children: (log.children || []).map(mapLog),
  });

  const rawItems = (Array.isArray(stored) ? stored : []).filter((item) => !(
    item?.kind === "text" && item.textKind === "narration" && item.pending
  )).map((item): ProcessTimelineItem | null => {
    if (item.kind === "text") {
      return {
        ...item,
        pending: false,
        contentExpanded: item.textKind === "reasoning" ? false : item.contentExpanded,
        childrenExpanded: true,
        children: (item.children || []).map(mapLog),
      };
    }
    if (item.kind === "todo") {
      const todos = normalizeTodoItems(item.todos);
      if (!todos?.length) return null;
      return {
        kind: "todo",
        id: item.id || "todo_current",
        title: item.title || "任务清单",
        todos,
        counts: todoCounts(todos),
      } satisfies ProcessTimelineTodoItem;
    }
    return mapLog(item);
  }).filter((item): item is ProcessTimelineItem => item !== null);

  const items = reorganizeSubagentItems(rawItems);

  const hasReasoning = items.some((item) => item.kind === "text" && item.textKind === "reasoning");
  const reasoning = String(reasoningContent || "").trim();
  if (!hasReasoning && reasoning) {
    items.push({
      kind: "text",
      id: "history_reasoning",
      textKind: "reasoning",
      content: reasoning,
      pending: false,
      contentExpanded: false,
    });
  }
  return items;
}
