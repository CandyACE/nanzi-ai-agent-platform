# 智能委派与编排 (Orchestration & Intelligent Delegation)

## Purpose
未指定专家时，系统直接将请求交给默认 `Main` 智能体。Main 根据自身 Prompt、可用能力、工具、权限和委派门禁决定直接回答，或调用子代理完成垂直任务。指定专家时直接加载该专家，原有指定专家逻辑保持不变。

`RouterService` 仅兼容保留，用于旧调用、路由常量和缓存失效；它不再是未指定专家请求的默认运行时入口。

## Requirements
### Requirement: Default Main Delegation
The system SHALL send requests without an explicit agent directly to the default `Main` agent, without invoking an outer semantic router.

#### Scenario: Main Answers Directly
- **WHEN** user sends a query without `agent_id`, `agent_name`, or `version_id`
- **THEN** system loads the default `Main` agent directly
- **AND** Main may answer with its own prompt and tools without calling a sub-agent

#### Scenario: Main Delegates on Demand
- **WHEN** Main determines that a task needs a vertical expert
- **THEN** Main may call `sub_agent_call` for one dependent task
- **OR** Main may call `sub_agent_batch_call` for independent tasks
- **AND** the platform validates candidate availability, user permission, self-delegation, duplicate calls, timeout, result size, and maximum nesting depth
- **AND** Main synthesizes the returned results for the user

#### Scenario: Direct Agent Selection
- **WHEN** request includes `agent_id`, `agent_name`, or `version_id` (including Embed expert mode or `@` mention)
- **THEN** system directly loads the specified agent
- **AND** sets `route_hints.direct_agent_selection = true` (disables main-assistant data hallucination guard)

### Requirement: Implementation Details
The system MUST implement the following data flow and API boundaries to support unified entry and delegation.

#### Data Flow
1. **输入**: 用户 Query + 对话历史 (Conversation History) + 可选 `last_agent_name`。
2. **处理**:
   - 若未显式指定智能体：直接加载默认 `Main`，不调用外层语义 Router。
   - 构建 Main Prompt，按权限注入可访问资源、历史摘要、技能和工具信息。
   - Main 按需调用 `sub_agent_call` / `sub_agent_batch_call`，平台对委派目标和执行边界做门控。
3. **输出**: Main 或指定专家的流式回答，以及可选的子代理 trace。

#### API Definitions
**默认 Main 入口**
```python
async def resolve_agent_config(
    self,
    *,
    agent_id: Optional[int] = None,
    agent_name: Optional[str] = None,
    version_id: Optional[int] = None,
    ...
) -> AgentConfig
```
- 未提供显式标识时返回默认 `Main` 配置；提供标识时返回指定专家配置。
- 对话历史、资源目录和技能等用于 Prompt 组装，不作为外层语义路由输入。

#### Configuration
- **Main Prompt**: 来自默认 Main 的已发布版本，并由 PromptAssembler 注入权限范围、工具和运行时上下文。
- **Delegation tools**: `sub_agent_call` / `sub_agent_batch_call` 受用户权限、目标状态、递归深度、超时和结果大小门禁约束。
- **Compatibility**: `RouterService.DEFAULT_SYSTEM_PROMPT`、`route_query()` 和会话亲和性相关实现仅供旧调用或兼容测试，不参与当前默认 Main 主链路。

## History
- **2026-01-05**: 增加上下文感知能力 (`history` 参数)，优化多轮对话路由准确率。
- **2026-06**: 问候/联网启发式短路；ChatBI 会话粘性修正（`should_inherit_data_agent_session`）；专家直选 `direct_agent_selection`；路由历史上下文注入「禁止机械沿用」提示。
- **2026-07**: ChatBI 会话亲和性三态（仅 `BREAK` 启发式离开；`UNCERTAIN` 进语义路由）。
- **2026-08-27**: 未指定专家改为直接进入默认 Main，由 Main 按需智能委派；指定专家逻辑保持不变；外层 Router 不再参与默认主链路。
