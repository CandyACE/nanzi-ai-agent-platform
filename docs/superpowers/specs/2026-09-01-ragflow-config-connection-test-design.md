# RAGFlow 元数据连接配置分组与连接测试设计

## 背景

系统配置中的 `metadata_provider` 选择 `ragflow` 后，需要填写 `ragflow_api_url` 和 `ragflow_api_key`。当前两项配置与其他参数以相同的平铺行展示，用户不容易确认它们属于同一组，也没有办法在填写后立即验证 RAGFlow 是否可用。

## 已确认的方案

采用方案 A：在元数据配置区域增加浅蓝色底色、圆角和细边框的“RAGFlow 连接配置”分组，分组内放置服务地址和 API Key；“测试连接”按钮放在 API Key 输入框下方，与测试状态文案同行。

测试时使用当前表单值，即使配置尚未保存也可以测试；测试成功后不自动保存。用户仍需点击页面的统一保存操作保存配置。

## 用户流程

1. 用户将 `metadata_provider` 切换为 `ragflow`。
2. 页面显示“RAGFlow 连接配置”分组，包含服务地址和 API Key。
3. 用户填写或修改 URL、API Key，点击“测试连接”。
4. 页面将当前表单值提交给后端。API Key 输入框中的脱敏值不直接提交真实密钥，而由后端读取已保存的密钥；用户新填写的密钥可用于本次测试。
5. 后端用这组临时配置向 RAGFlow 发起一次数据集列表请求：`GET /api/v1/datasets?page=1&page_size=1`。
6. 成功时显示“连接成功”，并补充本次返回的数据集数量；失败时显示可读的失败原因。
7. 测试结果不改变配置快照，也不触发保存；用户点击统一的“保存变更”后才写入系统配置。

## 前端设计

### 分组布局

- 仅在 `metadata_provider === 'ragflow'` 时展示分组。
- 分组包住 `ragflow_api_url` 和 `ragflow_api_key` 两行，使用现有系统配置页的间距、圆角和蓝色主题。
- 使用浅蓝色背景与细蓝色边框，不使用紫色高亮。
- API Key 保持现有密码显示/隐藏能力。
- 测试按钮放在 API Key 输入框下方，避免桌面端输入框过窄；状态文字与按钮同行。
- 移动端分组内保持单列布局，按钮和状态文字允许自然换行，不撑破页面。

### 状态

- 默认：按钮文案为“测试连接”，可点击条件为 URL 和 API Key 已配置，或脱敏 API Key 可回退到已保存密钥。
- 请求中：按钮显示“测试中…”，禁止重复点击。
- 成功：显示绿色状态，如“连接成功 · 已获取 N 个数据集”。即使列表为空，也显示连接成功并说明当前没有数据集。
- 失败：显示红色状态和后端返回的安全错误信息，不展示 API Key。
- URL 或 API Key 不完整时，在前端阻止请求并提示先补全配置。
- 切换 `metadata_provider` 或修改 URL/API Key 后，清除旧的测试状态，避免旧结果误导用户。

## 后端设计

### 接口

复用系统配置测试接口：

`POST /api/portal/system/test-connection/ragflow_metadata`

使用现有 `element:system:config_save` 权限，与系统配置页其他连接测试保持一致。

请求体增加 RAGFlow 测试字段：

```json
{
  "ragflow_api_url": "https://ragflow.example.com",
  "ragflow_api_key": "new-key-or-empty",
  "use_saved_api_key": false
}
```

约定：

- `use_saved_api_key=true` 时，后端只从配置服务读取已保存的 `ragflow_api_key`，前端不回传脱敏值。
- 用户新填入 API Key 时，`use_saved_api_key=false`，仅用于本次请求，不写入配置。
- 空 URL、缺少有效 API Key 时返回失败结果，不发起外部请求。
- 使用 `RagFlowClient(config_prefix="ragflow", override_url=..., override_key=...)`，避免误读常规知识库的 `knowledge_ragflow_*` 配置。
- 调用 `list_datasets(page=1, page_size=1)`，确保一次测试最多发起一次数据集列表请求。
- 返回统一的 `status`、`message`、`dataset_count`；不在日志、响应或异常中输出 API Key。

### 错误处理

- RAGFlow HTTP 错误、认证失败、URL 无法连接和超时都转换为失败响应。
- 后端保留现有权限校验和错误处理风格，不扩大为数据集管理权限。
- 该测试只验证连接及列表接口可用性，不同步数据集、不创建资源、不修改 RAGFlow。

## 测试与验收

### 后端

- 测试临时 URL/API Key 被传入 RAGFlow 客户端。
- 测试脱敏 API Key 会回退到已保存密钥，明文密钥不会出现在响应或日志断言中。
- 测试 `list_datasets` 使用 `page=1`、`page_size=1` 且只调用一次。
- 测试配置缺失、RAGFlow 请求失败时返回失败结果。

### 前端

- 契约测试确认 RAGFlow 两个配置项被同一分组包裹。
- 契约测试确认测试按钮、请求路径、加载态和成功/失败状态存在。
- 前端类型检查通过。
- `git diff --check` 通过。

### 未包含范围

- 不新增数据库迁移。
- 不自动保存配置。
- 不在测试按钮中执行数据集同步或权限同步。
- 不改变常规知识库 `knowledge_ragflow_*` 配置和已有 RAGFlow 管理页行为。
