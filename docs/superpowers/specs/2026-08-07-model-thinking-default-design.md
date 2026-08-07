# 模型默认思考模式语义调整设计

## 目标

将 `thinking_only` 的语义调整为“是否默认思考模式”。它只参与模型注册配置在后端解析时的默认值计算；前端传入的本次会话思考开关覆盖不受 `thinking_only` 影响。

## 语义

- `thinking_enable=false`：模型不具备平台思考能力，忽略前端要求开启思考。
- `thinking_enable=true` 且 `thinking_only=true`：后端未收到会话覆盖时默认开启思考。
- `thinking_enable=true` 且 `thinking_only=false`：后端未收到会话覆盖时默认关闭思考。
- 前端显式传入 `thinking_enable=true`：只要模型具备思考能力，就开启本次会话思考。
- 前端显式传入 `thinking_enable=false`：只要 `allow_disable_thinking=true`，就关闭本次会话思考；`thinking_only` 不参与该判断。
- `reasoning_effort` 仅在最终思考开启时生效，否则清空。

## 实现边界

后端在 `resolve_reasoning_settings` 中区分“注册模型默认思考状态”和“模型是否具备思考能力”。`thinking_only` 只用于计算没有会话覆盖时的初始状态；请求覆盖分支只校验模型能力和 `allow_disable_thinking`。

前端模型思考面板将注册模型的初始状态显示为 `thinking_enable && thinking_only`，但只要模型具备思考能力就允许通过会话开关显式开启；当当前状态为开启时，关闭动作由 `allow_disable_thinking` 控制。接口字段名保持不变，避免数据库迁移和 API 兼容性影响。管理页将字段文案改为“默认思考模式”，避免继续表达“只能思考”的旧语义。

## 测试

- 后端解析测试覆盖：默认开启、默认关闭、显式开启不受 `thinking_only` 影响、显式关闭只受 `allow_disable_thinking` 影响、非思考模型不能被开启。
- 前端契约测试覆盖：默认状态使用 `thinking_only`，开启状态允许手动打开，关闭权限不再由 `thinking_only` 参与判断；管理页使用“默认思考模式”文案。
- 运行现有思考配置相关后端测试和前端契约测试。
