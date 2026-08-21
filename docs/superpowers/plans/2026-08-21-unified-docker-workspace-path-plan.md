# Docker Unified Workspace Path Implementation Plan

**目标：** 让 Docker 沙箱模式下 Bash 与 Read/Write/Edit/Glob/Grep 统一使用 `/workspace` 作为用户工作区逻辑根目录。

**方案：** Docker 继续把 `<agentscope_workspace_root>/<user_key>` 挂载到容器 `/workspace`。宿主机上的 AgentScope 文件工具通过安全路径适配器把 `/workspace/...` 映射回同一个用户根目录；Docker 模式系统提示只向模型暴露容器逻辑路径，不暴露宿主机物理路径。路径适配仅作用于 Docker 沙箱，其他 local/E2B/SSH 策略保持原有行为。

**验证：** 先用回归测试证明 `/workspace` 路径映射、越界拒绝和 Docker 提示契约失败，再实现适配器并运行工作区、工具绑定、提示词和静态检查。
