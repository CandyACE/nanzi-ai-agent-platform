# 浏览器自动化工具显式配置设计

## 目标

移除浏览器自动化工具的全局隐式注入，改为智能体版本在后台通过“浏览器自动化”工具分组显式配置。默认智能体不再携带浏览器工具 schema；显式勾选后保持现有浏览器运行、权限和面板事件行为。

## 范围与兼容策略

- 保留浏览器工具在 `ToolRegistry` 中的注册，确保显式配置仍能解析和执行。
- 从 `ToolRegistry.get_system_implicit_tools()` 移除全部浏览器工具。
- 不迁移已有智能体版本的工具配置；历史版本不自动获得浏览器工具，管理员需要重新勾选。
- 不新增数据库字段或迁移 SQL，沿用现有版本 `tools` 列表持久化契约。
- 前端工具配置页新增“浏览器自动化”静态分组，支持分组全选和单工具选择。

## 运行时数据流

1. 智能体后台将选中的浏览器工具名称写入版本 `tools` 列表。
2. `AssistantAgentRunner` 通过现有 `ToolRegistry.get_runtime_tools()` 解析显式工具。
3. 未配置浏览器工具时，`get_system_implicit_tools()` 不再返回任何浏览器工具，模型请求不携带浏览器 schema。
4. 已配置浏览器工具时，沿用现有 `RuntimeToolSpec`、AgentScope Toolkit、权限中间件、浏览器事件和会话面板链路。

## 配置分组

“浏览器自动化”包含以下 19 个静态工具：

`browser_open`、`browser_snapshot`、`browser_click`、`browser_fill`、`browser_scroll`、`browser_press`、`browser_wait_for`、`browser_select_option`、`browser_read_visible`、`browser_hover`、`browser_drag`、`browser_back`、`browser_forward`、`browser_reload`、`browser_tabs`、`browser_switch_tab`、`browser_close_tab`、`browser_upload`、`browser_download`。

## 测试策略

- 后端测试确认浏览器工具仍可通过显式配置解析，但不出现在系统隐式工具集合中。
- 前端契约测试确认“浏览器自动化”分组存在、包含全部 19 个工具，并继续使用现有分组全选契约。
- 运行已有浏览器事件、工具注册和 AgentScope 工具解析回归测试。
- 不启动 `./dev.sh`，由用户自行启动服务进行页面手测。
