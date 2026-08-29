# 容器路径读工具 Bash 降级设计

## 背景

Docker 沙箱中 Bash 使用容器命名空间（例如 `/workspace/public/docs`），而
Read/Glob/Grep 默认由宿主侧 LocalWorkspace 执行。模型偶尔把容器内部或
Docker daemon 可见、宿主文件工具不可见的路径传给 Read/Glob/Grep，宿主路径
映射会返回 `container-only path cannot be used by host file tools`，当前请求随即
失败。

## 目标

当宿主文件工具仅因为容器路径不可映射而读取失败时，自动把读请求降级到同一
Docker 沙箱中的 Bash，尽可能完成读取；不改变写入安全边界，也不把普通越权或
权限拒绝伪装成可访问。

## 方案

在 Docker 工作区绑定阶段为 Read、Glob、Grep 保存可选的 sandbox Bash fallback。
宿主文件工具先按现有映射和授权规则执行；仅捕获明确的容器路径映射错误时，
调用 fallback。Bash 命令通过参数安全转义生成：Read 使用 `cat --`，Grep 使用
受限的 `grep`，Glob 使用受限的 `find`/匹配逻辑。fallback 结果复用现有工具结果
包装和错误增强逻辑。

`Write` 和 `Edit` 永远不走 Bash fallback。宿主侧授权失败、路径越界、其他用户
目录访问、Docker Bash 不可用或 Bash 命令失败时，保持原有拒绝/失败结果。不会
为了 fallback 接受任意宿主绝对路径；容器路径仍必须属于已声明的 Docker 挂载
命名空间。

## 数据流

1. 模型调用 Read/Glob/Grep。
2. 宿主 LocalWorkspace 执行路径映射和权限校验。
3. 若错误是明确的 container-only 映射错误，调用同一沙箱 Bash fallback。
4. fallback 成功则返回标准成功 ToolChunk；失败则返回原宿主错误与 Bash 错误的
   安全摘要，并继续现有自愈提示。

## 测试与验收

- 容器专属路径触发 Read fallback，并验证 Bash 收到安全转义后的命令。
- 容器专属路径触发 Glob/Grep fallback，并验证返回结果包装正确。
- 宿主可映射路径仍优先使用 LocalWorkspace，不调用 Bash。
- Write/Edit、越权路径和普通权限拒绝不调用 Bash。
- Bash fallback 异常不会吞掉原始错误，也不会泄露内部绝对路径。
- 运行相关 AgentScope workspace/tool 测试及 `git diff --check`。

