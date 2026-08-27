# Plan: 内置思考协议自动适配

> **For agent execution:** REQUIRED SUB-SKILL: Use `using-superpowers` and `test-driven-development` while implementing this plan.

**目标：** 在 AgentScope OpenAI-compatible 模型工厂中根据已配置的供应商自动生成关闭/开启思考所需的请求字段，让用户无需选择协议。

**实现位置：** `app/services/ai/runtime/agentscope/models.py`；测试集中在 `tests/ai/runtime/test_agentscope_llm_factory.py`。

## 任务 1：先锁定协议矩阵

- 增加 Kimi、智谱、火山、DashScope、SiliconFlow、Ollama 的请求体测试。
- 增加 OpenAI/Azure 不注入供应商扩展字段的测试。
- 增加 `other`/空 provider 继续使用旧 `chat_template_kwargs` 的回归测试。
- 先运行测试，确认新增用例在当前实现下失败。

## 任务 2：实现内置协议解析

- 增加私有 provider/model 归一化和协议解析函数。
- 将请求体生成拆为 DeepSeek V4、`thinking.type`、`enable_thinking`、`think`、旧模板参数五种策略。
- 保持已知 provider 不使用旧模板字段；未知自定义网关保持旧行为。

## 任务 3：同步工具调用重试路径

- 让已有思考模式下强制 `tool_choice` 的重试逻辑，按当前 provider 策略生成关闭思考请求体。
- 回归现有 DeepSeek V4 重试，并覆盖至少一种非 DeepSeek 协议的禁用字段。

## 任务 4：验证与交付

- 运行模型工厂及 fallback/流式相关针对性测试。
- 运行修改 Python 文件的编译检查、前端已有契约检查（若受影响）和 scoped `git diff --check`。
- 不启动服务、不操作数据库、不提交代码；明确告知用户需自行重启服务验证真实供应商接口。
