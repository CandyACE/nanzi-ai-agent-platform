# Echo MCP 认证诊断返回设计

## 目标

在内置 Echo MCP 的调用结果中展示认证处理过程，帮助平台管理员确认
`Authorization: Bearer ...` 和 `X-Nanzi-User-Assertion` 是否被正确传递、校验和解析，
同时避免回显完整凭证。

## 返回设计

在 `diagnostics` 中增加：

- `authorization_masked`：脱敏后的 Authorization 值；
- `user_assertion_masked`：脱敏后的用户身份断言；
- `processing_log`：按处理顺序排列的诊断步骤。

脱敏值只保留首尾少量字符，中间统一替换为 `***`。完整 Authorization、JWT 原文和
JWT Payload 不写入响应，也不写入服务端日志。已有的验签结果、用户上下文、扩展字段、
智能体上下文和标准 claims 继续返回。

## 处理流程

1. 读取 Authorization 请求头并生成脱敏展示值；
2. 校验 Authorization Bearer Token；
3. 读取 `X-Nanzi-User-Assertion` 并生成脱敏展示值；
4. 校验 EdDSA 签名、`kid`、issuer、audience、时效和必需 claims；
5. 解析用户、扩展字段、智能体和请求信息；
6. 返回处理结果和步骤日志。

缺少可选的用户身份断言时，保留原有兼容行为：返回
`user_assertion_received=false` 和 `user_assertion_valid=false`。Authorization 或用户断言
校验失败时，继续沿用 Echo 原有的拒绝调用行为；异常只使用固定的安全错误信息，
不返回完整凭证。

## 测试范围

- 成功请求包含脱敏凭证和完整处理步骤；
- 脱敏结果不包含完整 Authorization 或用户断言；
- 无用户断言时记录未收到状态；
- 无效 Authorization 或用户断言时不泄露原文；
- 现有 Echo MCP、用户断言验签和 API 合约测试保持通过。
