const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "webp", "gif"]);

export function normalizeAttachmentExt(ext?: string, url?: string): string {
  let normalized = (ext || "").toLowerCase().replace(/^\./, "");
  if (!normalized && url) {
    const path = url.split("?")[0] || "";
    const segment = path.split("/").pop() || "";
    const dot = segment.lastIndexOf(".");
    normalized = dot >= 0 ? segment.slice(dot + 1).toLowerCase() : "";
  }
  return normalized;
}

export function isImageAttachment(file: {
  ext?: string;
  url?: string;
}): boolean {
  return IMAGE_EXTS.has(normalizeAttachmentExt(file.ext, file.url));
}

/** 输入框/气泡内图片缩略图 URL（本地上传 vs 服务器文件） */
export function getAttachmentPreviewUrl(file: {
  url?: string;
  type?: string;
  ext?: string;
}): string | null {
  if (!file.url || !isImageAttachment(file)) return null;
  if (/^https?:\/\//.test(file.url)) return file.url;
  // 历史公共静态托管（兼容旧消息）
  if (file.url.startsWith("/static/uploads/")) return file.url;
  if (file.url.startsWith("/api/")) return file.url;
  // 用户私有 uploads / 工作空间路径：走鉴权预览 API
  return `/api/v1/chat/fs/preview?path=${encodeURIComponent(file.url)}`;
}

/** `/api/...` 预览需带鉴权头，不能直接塞进 <img src> */
export function attachmentPreviewNeedsAuthFetch(previewUrl: string | null | undefined): boolean {
  if (!previewUrl) return false;
  if (previewUrl.startsWith("/static/")) return false;
  if (/^https?:\/\//.test(previewUrl)) return false;
  if (previewUrl.startsWith("blob:") || previewUrl.startsWith("data:")) return false;
  return previewUrl.startsWith("/api/");
}

/** 附件在服务器上的绝对路径（供 AI 上下文与工具使用） */
export function getServerAttachmentPath(file: {
  type?: string;
  url?: string;
  filename?: string;
}): string {
  if (file.type === "skill") {
    // 技能**不给任何文件系统路径**。SKILL.md 正文已由后端预载进本轮上下文，而技能文件的
    // 真实位置随「公共/个人」与「沙箱策略」变化：曾经写死的
    // `/app/data/skills/<id>/SKILL.md` 对个人技能（真身在 agent_workspaces/<user_key>/skills/）
    // 与 Docker/K8s 沙箱（只有 /workspace，没有 /app/data）都不成立，模型照抄必然
    // File does not exist。真实目录由模型按需调用 list_accessible_directories 查询。
    // 被禁技能同样不给出路径（这条口径由 attachment hint 的禁用文案保证）。
    return "";
  }
  if (file.type === "local_file" || file.type === "local_dir") {
    return file.url || "";
  }
  const url = file.url || "";
  if (url.startsWith("/static/uploads/")) {
    const fileName = url.split("/").filter(Boolean).pop() || file.filename || "";
    return `/app/data/uploads/${fileName}`;
  }
  if (url && !url.startsWith("http")) {
    return url;
  }
  const fileName = url.split("/").filter(Boolean).pop() || file.filename || "";
  return `/app/data/uploads/${fileName}`;
}
