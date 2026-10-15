/**
 * 平台支持的 HTTP 方法**唯一来源**。
 *
 * 与运行时 ``GenericApiToolFactory._execute_request`` 的支持集合严格一致：
 * GET 走 query，POST/PUT/PATCH/DELETE 走 JSON body，其余方法运行时直接返回
 * ``[Error] Unsupported method``——所以 HEAD/OPTIONS **不能**出现在静态可选项里，
 * 配了也永远失败（历史遗留的死选项，本次一并删掉）。
 *
 * 契约测试 ``tests/frontend/test_api_tool_method_list_contract.py`` 钉住：
 * 本清单 == 运行时支持集合。
 */
export const SUPPORTED_HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] as const

export type SupportedHttpMethod = (typeof SUPPORTED_HTTP_METHODS)[number]

/** 方法是否被运行时支持（大小写不敏感；空值视为不支持）。 */
export const isSupportedMethod = (method: string | null | undefined): boolean =>
    SUPPORTED_HTTP_METHODS.includes(
        String(method || '').trim().toUpperCase() as SupportedHttpMethod,
    )
