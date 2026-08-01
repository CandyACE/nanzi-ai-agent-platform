# 运行时模型查询设计

## 目标

让用户询问“当前模型是什么”时，平台返回本轮真实生效的模型信息，而不是让模型根据训练记忆猜测；同时让智能体在需要时可以通过只读工具查询同一份运行时信息。

## 背景与边界

当前模型名会参与 LLM 实例创建、AgentScope 调用和观测记录，但没有进入模型可见上下文。现有链路还可能把配置别名解析成实际 `model_id`，并存在调试覆盖、合成模型和 fallback，因此不能只读取 `ChatConfig.model_name`。

本次只覆盖本轮主智能体/当前调用阶段的模型身份查询，不修改模型选择优先级，不暴露 API Key、Base URL 或其他凭据，不运行服务启动脚本。

## 方案

新增一个共享的运行时模型信息解析边界，返回：

- 配置层模型名或别名；
- 解析后的实际模型 ID；
- 模型来源（智能体配置、调试覆盖、系统默认等）；
- 当前阶段（主智能体、合成或 fallback）；
- 是否为 fallback。

`AgentConfigProvider.get_configured_llm()` 复用该解析边界，避免工具、元事件和实际 LLM 调用各自解析出不同结果。

用户自询问由 AgentService 在调度模型前识别并直接生成安全回答，保证不依赖模型是否主动调用工具。与此同时，将 `get_current_model` 作为只读 system implicit tool 注册，使普通模型流程也能查询同一份信息。

## 数据流

```text
ChatConfig + debug options + DB model registry
        -> runtime model resolver
        -> effective model info
          -> AgentService direct answer
          -> get_current_model tool
          -> LLM factory / meta event / trace
```

## 安全与错误处理

- 仅返回模型标识、阶段和来源，不返回凭据、地址或完整内部配置。
- 模型注册表查询失败时保留可确定的配置模型，并明确标记 `resolution_status`，不得伪造实际 `model_id`。
- 不把用户输入中的模型名当作运行时事实。
- 合成/fallback 阶段必须显式标记，避免把配置模型误称为实际执行模型。

## 验收标准

1. 配置模型、系统默认模型、调试覆盖和注册表别名均能得到一致的有效模型信息。
2. 用户直接询问当前模型时，平台不发起一次依赖模型自报的普通回答，并返回实际可确定的信息。
3. `get_current_model` 在 system implicit tools 中可发现、可调用，且不泄露敏感配置。
4. 现有模型调用、SSE meta、trace 和无关工具行为不改变。
5. 定向测试通过；未运行的服务启动、真实供应商 API 和浏览器验收明确标注为未验证。
