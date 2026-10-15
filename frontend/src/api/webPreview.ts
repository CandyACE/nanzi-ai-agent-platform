/**
 * 网页预览内嵌实测接口。
 *
 * 判定「目标网页能否被内嵌」这件事必须由服务端做：`X-Frame-Options` 与 CSP
 * `frame-ancestors` 都是响应头，跨域 iframe 里前端读不到，也无法自证被拦
 * （被拦时 `onload` 仍会触发）。旧实现只能按域名名单猜，于是误拦了 baidu.com。
 */
import axios from '@/utils/axios'
import type { EmbedProbeOutcome } from '@/utils/webPreviewEmbed'

/** 后端 `/api/portal/web-preview/embed-check` 的响应体。 */
export interface EmbedCheckResponse {
  url: string
  final_url: string
  /** true=实测可嵌；false=实测会被拦截；null=未取得结论（不可达等）。 */
  embeddable: boolean | null
  reason: string
  signals: Record<string, string>
}

/**
 * 实测目标网页是否允许被内嵌。
 *
 * 探测失败（后端异常、网络中断）不抛给调用方，而是统一折算成
 * `embeddable: null`，让调用方按「未取得结论」降级处理。
 */
export async function checkWebPreviewEmbed(url: string): Promise<EmbedProbeOutcome> {
  try {
    const response = await axios.post<EmbedCheckResponse>(
      '/api/portal/web-preview/embed-check',
      { url },
      { timeout: 20000 },
    )
    const data = response.data || ({} as EmbedCheckResponse)
    return {
      embeddable: typeof data.embeddable === 'boolean' ? data.embeddable : null,
      reason: data.reason || '',
      signals: data.signals || {},
    }
  } catch (error) {
    console.warn('[WebPreview] 内嵌实测未取得结论，降级为经验预判', error)
    return { embeddable: null, reason: '实测接口不可用' }
  }
}
