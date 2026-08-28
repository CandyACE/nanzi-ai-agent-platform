# AgentScope 统一工具调用超时设计

## 1. 背景与目标

当前 AgentScope 运行时已经把大多数平台工具转换为 `RuntimeToolSpec`，但统一包装默认没有工具级超时；原生 Bash、Read、Write、Edit、Glob、Grep 等工具还会经过 `AgentScopeNativeApprovalTool`，存在另一条调用路径。部分工具内部另有更短的 SQL、HTTP、浏览器或子智能体超时。

本设计新增系统配置 `agent_max_toolcall_timeout`，让所有 AgentScope 工具调用拥有可配置的统一执行时间。默认值为 120 秒；智能体版本可以覆盖全局值，工具自身的更短配置不再覆盖已选定的版本级或全局配置。

本次不删除或改写 SQL、HTTP、浏览器、E2B、SSH、调度任务等既有专项超时，也不改变 `agent_max_iterations` 的轮数语义。

## 2. 已确认的产品规则

### 2.1 系统配置

- 配置键：`agent_max_toolcall_timeout`
- 分类：`agent`
- 单位：秒
- 默认值：`120`
- 合法范围：`1–3600`
- 仅接受十进制整数数字
- 管理页面显示在 `agent_max_iterations` 下方
- 前端提供仅接受十进制数字的手动输入，并提供「−」「＋」步进按钮
- 步长为 1 秒，到达上下限时禁用对应按钮
- 后端保存接口对该键执行相同的整数和范围校验
- 历史缺失值、空值或运行时解析失败时回退到 120 秒

### 2.2 生效时机

每次构建 Agent 的工具集合时读取一次配置，形成当前请求的超时快照。配置修改通过现有系统配置服务刷新 Redis 和内存缓存，对后续新建的 Agent 请求生效；一个已开始的工具调用不在中途切换超时值。

### 2.3 最终超时计算

统一超时按配置优先级选择单一值：

```text
effective_timeout = 版本级配置值（非空） or 全局配置值 or 默认 120 秒
```

版本级配置优先于全局配置；版本级未配置时使用全局配置，非法值按未配置处理。工具规格自身的超时和工具调用显式传入的 `timeout` 参数不参与优先级计算，也不会覆盖已选定的统一配置值；统一包装器会将选定值应用到工具调用。AgentScope、MCP 服务、反向代理或外部数据源仍可能存在平台无法覆盖的基础设施硬限制。

## 3. 方案与架构

采用“统一超时策略 + 两条包装路径复用同一调用器”的方案。

### 3.1 配置解析与工具快照

新增 `app/services/ai/runtime/agentscope/tool_timeout.py`，负责：

1. 定义配置键、默认值、最小值和最大值；
2. 从 `ConfigService.get()` 读取配置；
3. 将缺失、空值、非整数、非有限值和越界值转换为安全的 120 秒默认值；
4. 提供工具规格批量应用函数，将所有 `RuntimeToolSpec` 设置为当前版本级或全局配置选定的统一值。

在 Agent 构建工具集合时读取一次全局配置，并接收当前 `ChatConfig` 的版本级覆盖，形成一次请求的超时快照，覆盖普通智能体、知识库智能体和 ChatBI：

- `app/services/ai/runners/assistant_agent_runner.py`
- `app/services/ai/runners/knowledge_agent_runner.py`
- `app/services/ai/runtime/agentscope/data_tools.py`

应用发生在工作区绑定前，使 `bind_configured_tools_to_workspace()` 复制或重绑工具时保留超时值。

### 3.2 统一调用器

在 `app/services/ai/runtime/agentscope/tools.py` 中抽取共享调用逻辑，覆盖：

- 普通异步 callable；
- 由遗留工具转换而来的同步 callable；
- 异步生成器，并以整个生成过程计算总超时；
- AgentScope 原生工具。

`RuntimeToolSpec.invoke()` 和 `AgentScopeNativeApprovalTool.__call__()` 都使用该调用器。超时通过 `asyncio.wait_for()` 或等价的异步超时边界实施；同步 callable 通过线程边界执行，使主请求能够按时返回。无法强制终止的同步线程仍必须依赖其现有的进程、HTTP 或数据库内部超时，不能假设线程取消会撤销外部副作用。

原生工具适配器继续保留权限检查、工作区路径检查、工具循环检测、工作区错误增强和证据记录，但不再绕过统一超时。对于原生 Bash：

- 未传入 `timeout` 时，若其输入 Schema 支持该字段，注入当前统一配置值；
- 已传入的毫秒值转换为秒后，重写为当前统一配置值；
- 继续尊重 AgentScope 自身的 600 秒最大限制；
- Docker、E2B、SSH 或 MCP 提供的 Bash 若不支持该字段，则由外层异步超时负责限制调用。

### 3.3 错误、审计与清理

工具超时时统一产生 `RuntimeTimeoutError`，错误详情包含工具名和生效秒数。普通工具和原生工具均发出开始、错误及耗时审计事件；超时工具不得登记成功证据。

超时路径继续执行已有清理逻辑：本地 Bash 终止进程组，子智能体关闭流并释放资源，MCP/异步流完成取消和会话清理。超时不自动重试，避免写操作、通知或外部 API 调用产生重复副作用。SSE、前端工具日志和终端错误沿用现有错误展示链路。

## 4. 配置页面与后端保存

### 4.1 后端

修改 `app/services/config_service.py` 的配置更新校验，仅对 `agent_max_toolcall_timeout` 增加纯整数和 `1–3600` 范围校验；其他系统配置保持现有兼容行为。系统配置 API 继续复用现有批量保存、审计和 Redis 刷新逻辑。

### 4.2 前端

修改 `frontend/src/views/SystemConfig.vue`：

- 在 `agent` 分类排序数组中把新键放在 `agent_max_iterations` 后面；
- 增加短描述和帮助说明，明确单位为秒、默认 120、范围 1–3600；
- 为该键增加仅接受数字的输入框和步进控件；
- 「−」「＋」按钮通过统一的数值调整函数更新字符串形式的配置值，以兼容现有批量保存 API；
- 组件禁用状态沿用系统配置权限和上下限规则；
- 其他数值配置控件保持不变。

## 5. 数据库迁移

新增两套独立迁移，不混用数据库方言：

- `db-prod/V132-add-agent-max-toolcall-timeout.sql`
- `db-prod-pg/V32-add-agent-max-toolcall-timeout.sql`

两份迁移分别使用 MySQL 的 `INSERT IGNORE` 和 PostgreSQL 的 `ON CONFLICT DO NOTHING`，向 `system_configs` 插入：

```text
key         = agent_max_toolcall_timeout
value       = 120
description = AgentScope 单次工具调用最大超时时间（秒），默认 120。
category    = agent
is_secret   = false
```

迁移只新增配置项，不直接修改本地或线上数据库。

## 6. 测试与验收

### 6.1 后端聚焦测试

- `tests/ai/runtime/test_agentscope_tooling.py`：验证普通工具使用默认全局超时、已有专项超时取更短值、超时错误和审计状态；
- 新增运行时超时测试：验证原生工具、同步 callable、异步生成器的超时边界，以及取消后的清理行为；
- 新增配置解析测试：验证默认值、非法值回退、范围边界和配置快照；
- 新增系统配置 API 测试：验证新键拒绝非数字、0、负数和超过 3600 的值；
- 新增迁移契约测试：验证 MySQL/PostgreSQL 两份迁移都包含正确键、默认值、分类和幂等写法。

每个新行为遵循先写失败测试、确认失败原因，再实现最小代码并验证通过。

### 6.2 前端契约测试

新增 `tests/frontend/test_system_config_toolcall_timeout_contract.py`，验证：

- 新配置出现在 `agent_max_iterations` 后面；
- 页面存在数字输入框和「−」「＋」按钮；
- 输入和粘贴内容只保留十进制数字；
- 步长、上下限和帮助文案存在；
- 保存仍走既有系统配置批量接口。

### 6.3 本地验证边界

允许执行不启动服务的聚焦 pytest、前端契约测试、`vue-tsc --noEmit`（从 `frontend/` 目录执行）和 `git diff --check`。不运行 `./dev.sh`、部署脚本或生产数据库操作。最终仍需用户在控制台启动服务后手工验证：

1. 系统设置中通过加减按钮保存 120、1、3600 秒边界；
2. 普通工具超时后前端显示终端错误；
3. Bash、MCP、ChatBI SQL 和子智能体分别验证版本级值优先、未配置时回退全局值，以及工具显式参数不会覆盖统一配置；
4. 修改配置后新请求使用新值，正在执行的旧请求不被中途改写。

## 7. 非目标与风险

- 不把 `agent_max_iterations` 改成时间预算；两者继续分别限制轮数和单次工具调用时长；
- 不删除各工具已有的内部超时；
- 不承诺强杀任意同步 Python 线程，具有阻塞外部副作用的同步工具仍需要自己的可取消执行机制；
- AgentScope、MCP 服务端或反向代理可能有更短的外部限制，平台统一配置不能覆盖这些边界；
- 配置保存后的实际生效依赖运行中的 Redis/数据库和用户手工重启或新建请求验证，本地静态测试不能替代真实服务验收。
