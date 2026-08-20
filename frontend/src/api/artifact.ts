import axios from '../utils/axios'
import type { StandardResponse, ListResponse } from './common'

/** 单条 AI 产物（Word/Excel/导出等）元信息 */
export interface ArtifactListItem {
  id: string
  filename: string
  artifact_type: string
  mime_type?: string | null
  size: number
  conversation_id?: string | null
  trace_id?: string | null
  created_at?: string | null
  expires_at?: string | null
  /** 相对下载地址：/api/v1/chat/generated-files/{id}?token={token} */
  download_url: string
}

export interface ArtifactListParams {
  page?: number
  page_size?: number
  artifact_type?: string
  /** 按生成该产物的 AI 消息 trace_id 过滤 */
  trace_id?: string
}

export const artifactApi = {
  list: (params: ArtifactListParams = {}) =>
    axios.get<StandardResponse<ListResponse<ArtifactListItem>>>(
      '/api/v1/chat/artifacts',
      { params },
    ),
  /** 会话内各 trace_id → 产物数量 的轻量映射（用于判断某条消息是否真有产物及数量角标） */
  countsByTrace: (conversationId: string) =>
    axios.get<StandardResponse<{ counts: Record<string, number> }>>(
      '/api/v1/chat/artifacts/counts',
      { params: { conversation_id: conversationId } },
    ),
}