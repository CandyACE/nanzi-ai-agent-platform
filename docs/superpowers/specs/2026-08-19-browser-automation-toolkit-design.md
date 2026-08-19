# 服务端自动化浏览器工具补齐设计

## 目标

在现有 `browser_open`、`browser_snapshot`、`browser_scroll`、`browser_click`、`browser_fill` 最小闭环上，补齐真实网站自动化需要的等待、键盘、下拉选择、内容读取、悬停、拖拽、历史导航、标签页和文件传输能力，同时保持截图查看器与 AI 控制权隔离。

## 设计决策

1. 所有 AI 交互工具继续使用 `snapshot_id + target_ref` 语义定位；不开放任意 CSS 选择器、JavaScript 或坐标点击。
2. 所有产生页面变化的动作执行后清理旧快照，并通过现有 `browser_refresh` 事件通知前端刷新截图；模型需要使用返回的最新快照继续操作。
3. 等待只允许有限条件：文本出现、URL 包含、目标出现、页面状态变化；超时时间服务端限制在 10 秒内，避免工具循环长时间阻塞。
4. `Enter`、文件上传和可能提交外部副作用的动作进入现有 guarded 权限判断；高风险判断只使用通用动作语义、控件角色和当前页面状态，不硬编码任何业务领域词。
5. 标签页只保存在当前浏览器 Worker 内存中，使用稳定的短 `tab_id`，不把 Playwright 对象或敏感令牌暴露给模型。
6. 上传文件只允许当前用户会话附件、用户工作目录或已发布生成文件；下载文件通过现有能力链接发布，不返回服务器物理路径。

## 工具范围

- `browser_press`：对快照目标或当前焦点发送 Enter、Tab、Escape、方向键及组合键。
- `browser_wait_for`：等待文本、URL、目标或页面状态，返回最新语义快照。
- `browser_select_option`：选择原生或 ARIA 下拉框的选项。
- `browser_read_visible`：读取当前视口内非交互页面文字，补足长列表等内容理解。
- `browser_hover`、`browser_drag`：支持悬停菜单、日期选择器、滑块和拖拽排序。
- `browser_back`、`browser_forward`、`browser_reload`：支持历史导航和刷新。
- `browser_tabs`、`browser_switch_tab`、`browser_close_tab`：管理多标签页面。
- `browser_upload`、`browser_download`：安全上传当前用户文件和发布页面下载结果。

## 错误与安全

- 快照不存在、页面变化或目标指纹不匹配时返回可恢复的过期快照错误，提示先重新快照。
- 页面导航和新标签 URL 继续经过 SSRF/协议校验。
- 密码、上传路径、下载服务器路径不进入工具输出、审计或 SSE；下载只返回能力链接。
- CAPTCHA 或人工接管时，AI 工具等待人工释放，不抢占用户操作。

## 验证

- 为每个新增 Worker 动作增加失败优先的单元测试。
- 增加工具注册、权限策略、事件刷新、敏感信息脱敏和文件边界测试。
- 运行浏览器服务目标测试、前端契约测试、`vue-tsc --noEmit`、Python 编译和 `git diff --check`；不启动 `./dev.sh`，不执行数据库迁移。
