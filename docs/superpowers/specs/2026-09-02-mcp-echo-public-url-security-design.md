# Echo MCP 公网地址与 Host 白名单设计

## 目标

让内置 Echo MCP 在生产环境使用 `APP_PUBLIC_URL` 时，自动把该公网地址的 Host 和 Origin 加入 MCP 传输安全白名单，同时让创建 Echo 时保存的 `sse_url` 与公网地址一致；未配置时保持本地 `request.base_url` 和 localhost 行为。

## 方案

### 配置来源

- `APP_PUBLIC_URL` 继续使用现有平台配置，不新增管理页面字段。
- 配置值应为平台对外访问的 Origin，例如 `https://mcp.example.com` 或 `http://103.79.25.80:8001`。
- `APP_PUBLIC_URL` 配置后，后端解析其 scheme、hostname 和可选 port，生成 FastMCP 的 `allowed_hosts` 与 `allowed_origins`。
- 未配置或为空时，不传自定义传输安全配置，让 MCP SDK 保留当前 localhost 自动白名单行为。

### Echo 地址生成

创建或恢复 Echo MCP 时，优先使用 `settings.APP_PUBLIC_URL` 去掉末尾斜杠后的值生成 `/mcp/echo/mcp`；只有在该配置为空时，才使用当前请求的 `request.base_url`。

### 安全边界

- 保持 DNS rebinding 防护开启。
- 不使用 `allowed_hosts=["*"]`。
- `APP_PUBLIC_URL` 的 Host 是唯一新增的生产白名单来源；本地未配置时仍只允许 SDK 默认的 localhost Host。
- `allowed_origins` 使用 `APP_PUBLIC_URL` 的完整 scheme + authority；MCP 服务端调用通常没有 Origin，但保留正确配置以覆盖浏览器测试场景。

## 错误处理

若 `APP_PUBLIC_URL` 不是绝对 HTTP/HTTPS URL，或缺少 hostname，则不使用它生成白名单和 Echo 地址，回退到原有行为，避免应用导入阶段因为配置格式问题直接无法启动。测试覆盖该回退行为。

## 测试范围

- 公网 URL 含端口时，生成对应的 `hostname:port` Host 白名单和 Origin。
- 公网 HTTPS 域名无端口时，生成域名 Host 白名单和 HTTPS Origin。
- 未配置公网 URL 时，Echo 创建接口继续使用 `request.base_url`。
- 配置公网 URL 时，Echo 创建接口优先使用该地址。
- 现有 Echo 认证、工具调用和前端契约不改变。

## 不在本次范围

- 不新增前端 `allowed_hosts` 输入框。
- 不新增数据库字段或迁移。
- 不关闭 MCP DNS rebinding 防护。
- 不修改 SSE 与 Direct HTTP 的降级策略。
