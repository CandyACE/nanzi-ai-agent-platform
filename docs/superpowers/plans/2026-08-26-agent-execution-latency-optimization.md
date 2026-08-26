# 智能体执行链路低延迟优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏路由、权限、知识库、数据查询、委派、上下文安全和审计持久化语义的前提下，降低智能体首 token 延迟（TTFT）和长尾总耗时，优先治理执行链路中可重复、可测量的等待。

**Architecture:** 先建立按阶段的请求级观测，再针对已确认的瓶颈做局部优化。优化分为三层：模型调用前的重复 I/O 和同步文件扫描、模型调用中的 token 计数和多轮工具/修复预算、流式输出完成后的队列与审计收尾。所有缓存默认限制在进程或单请求范围，并保留权限和上下文安全的最终校验。

**Tech Stack:** Python 3.11、FastAPI、asyncio、SQLAlchemy Async、Redis、AgentScope 2.x、pytest。

---

## 范围与约束

- 目标指标是 TTFT、P50/P95 总耗时、模型调用次数、工具调用次数、DB/Redis 等待时间和 token 计数次数；不能只用单次总耗时判断优化是否有效。
- 必须区分冷启动/热缓存、自动路由/显式选择智能体、普通问答/知识库/数据查询、有无技能、有无工具、多轮修复和并发场景。
- 不增加新的“每轮意图识别模型调用”。当前路由器已经包含问候语、唯一候选、资源目录、结果追问等快速路径，应优先复用已有的 TurnDecision 和路由结果。
- 不通过降低权限检查、就绪检查、知识库 grounding、上下文 token guard、数据查询校验或审计持久化要求来换取延迟。
- 不在本计划中启动服务、执行部署脚本或操作生产数据库；服务重启和线上压测由用户在控制台执行。

## 阶段一：建立可比较的执行链路基线

**目标文件：**

- app/services/ai/agent_service.py
- app/services/ai/runtime/agentscope/event_stream.py
- app/api/v1/endpoints/chat.py
- tests/services/ai/test_agent_latency_observability.py

**实施步骤：**

- [ ] 在请求级 trace/context 中增加单调时钟阶段计时，使用 time.perf_counter()，至少覆盖以下阶段：
  - route_resolution
  - runtime_model_metadata
  - context_setup
  - skill_injection
  - memory_load
  - workspace_initialization
  - first_model_call_start
  - first_visible_token
  - tool_rounds
  - audit_finish
- [ ] 增加 TTFT、total_elapsed_ms、model_call_count、tool_call_count、queue_wait_ms 和 client_disconnected 等字段。
- [ ] 只记录阶段名称、耗时、计数和稳定的请求标识，不把用户原文、完整 prompt、密钥、完整工具参数写入性能指标。
- [ ] 在已有的 route status/execution_time_ms 观测基础上补充模型调用前和模型调用后的阶段，不改变事件顺序和用户可见文本。
- [ ] 为正常完成、模型异常、工具异常、客户端断开分别增加单元测试，确认计时 finally 不会遮蔽原始异常。

建议采用如下小型计时器，避免使用墙上时钟导致系统时间调整影响结果：

~~~python
class StageTimer:
    def __init__(self, clock=time.perf_counter):
        self._clock = clock
        self._started = clock()
        self._marks = {}

    def mark(self, name: str) -> None:
        now = self._clock()
        self._marks[name] = round((now - self._started) * 1000, 2)

    def elapsed(self, name: str, previous: str | None = None) -> float | None:
        if name not in self._marks:
            return None
        start = self._marks.get(previous, 0.0) if previous else 0.0
        return round(self._marks[name] - start, 2)
~~~

**验证命令：**

~~~bash
venv/bin/python -m pytest tests/services/ai/test_agent_latency_observability.py -q --confcutdir=tests/ai
git diff --check
~~~

**收益：** 能把“14.9 秒”拆成路由、上下文、技能扫描、模型首 token、工具轮次和审计收尾，避免把一个模型或外部数据源问题误判为 Python 调度问题；也为后续每项优化提供回归基线。

**代价与风险：** 每次请求增加少量计时和指标写入开销；观测字段如果设计不当可能泄露输入或工具参数；需要约束指标 cardinality，不能用用户原文作为标签。

## 阶段二：合并同一轮的重复配置、路由和上下文读取

**目标文件：**

- app/services/ai/agent_service.py
- app/services/ai/context_manager.py
- app/services/ai/router_service.py
- app/services/config_service.py
- app/services/ai/runners/assistant_agent_runner.py
- tests/services/ai/test_agent_execution_snapshot.py

**实施步骤：**

- [ ] 在同一轮请求内传递一个不可变的 runtime snapshot，包含已确认的智能体配置、TurnDecision、权限过滤后的数据集/工具结果和必要的运行时模型元数据，避免 route、context、dispatcher、runner 再次查询同一对象。
- [ ] 保留显式 version_id/agent_id/agent_name 的直接选择语义：直接选择可以跳过自动路由，但仍必须执行当前的权限、发布就绪和委派边界检查。
- [ ] 检查 _run_chat_turn_stream 中第一次 setup_context 与知识库补充 setup_context 的差异。只有知识库阶段真正改变数据集、工具或 grounding 约束时才执行增量补充；否则复用第一次结果。不能简单删除第二次 setup_context。
- [ ] 为 runner 中连续读取的工具循环配置提供请求级 get_many/config snapshot，尤其是 agent_max_iterations、工具循环检测相关配置和已有默认值。配置更新只保证对下一轮请求生效，不建立跨请求的永久配置缓存。
- [ ] 仅对互不依赖的 Redis/数据库读取做 asyncio.gather；每个子任务必须有明确的降级值，并保留 CancelledError 的传播：

~~~python
async def _safe_read(awaitable, default, *, label: str):
    try:
        return await awaitable
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("optional read failed: %s", label, exc_info=True)
        return default

memory, summaries = await asyncio.gather(
    _safe_read(load_memory(), [], label="memory"),
    _safe_read(load_summaries(), [], label="summaries"),
)
~~~

- [ ] 不使用 return_exceptions=True 后直接按固定类型解包；如果读取之间存在顺序依赖，继续保持顺序执行。
- [ ] 为自动路由、显式智能体、知识库补充、权限拒绝和配置读取失败补充 snapshot 一致性测试。

**收益：** 减少同一请求内重复的数据库/Redis往返和串行等待，降低模型调用前的 TTFT；runtime snapshot 还可以让后续 trace 清楚显示一次路由结果被哪些阶段复用。

**代价与风险：** 同一轮并行读取会提高瞬时连接池压力；snapshot 如果扩大范围，可能让请求继续使用本轮开始时的配置，而不是中途更新后的配置；错误的复用可能造成旧权限、旧数据集或旧工具清单泄漏。因此 snapshot 必须是请求级、不可变且在权限过滤之后形成，不能替代每轮必要的 readiness/permission 校验。

## 阶段三：技能元数据目录建立可失效快照

**目标文件：**

- app/services/ai/skill_resolver.py
- app/services/ai/agent_service.py
- tests/services/ai/test_skill_resolver_cache.py

**实施步骤：**

- [ ] 先分别测量 global skills、personal skills 的冷扫描和热扫描耗时，以及同一请求内 list_skill_metas、resolve_skills_from_query、scan_relevant_skills、load_skill_md_content 的重复调用次数。
- [ ] 为技能元数据建立有界的进程级快照，键至少区分全局技能目录指纹、用户个人技能目录指纹和必要的用户授权范围；不能把不同用户的个人技能混入同一个缓存键。
- [ ] 目录指纹可使用目录 mtime、文件名/大小/mtime 的稳定摘要或现有技能变更通知；设置有限 TTL 作为兜底。管理员新增、修改、删除技能和用户个人技能变化时主动失效。
- [ ] load_skill_md_content 不再为了定位一个技能重复完整扫描目录；先从元数据快照解析路径，再执行路径授权和文件读取。
- [ ] 仅在冷扫描这个同步文件系统操作上考虑 asyncio.to_thread；热路径不得每次都创建线程任务。to_thread 改善的是事件循环被阻塞的问题，不一定降低单请求墙上时间，线程池过载还可能使并发更慢。
- [ ] 保留个人技能覆盖全局技能、技能白名单、路径授权、SKILL.md 解析和 using-superpowers 首轮预加载语义。不要把完整 SKILL.md 内容无限期放入全局缓存。
- [ ] 增加目录变更后的立即失效测试、不同用户隔离测试、冷/热扫描耗时测试和非法路径测试。

**收益：** 技能目录较大或每轮会重复扫描时，可以直接减少文件系统遍历和 frontmatter 解析，是模型调用前较有希望的低风险收益点。

**代价与风险：** 缓存失效不完整会让新技能、禁用技能或权限变更延迟生效；快照会占用内存；对热路径盲目使用 to_thread 只能改善 event loop fairness，无法保证 TTFT 下降，甚至会增加线程池排队。

## 阶段四：合并模型调用中的 token 计数

**目标文件：**

- app/services/ai/runtime/agentscope/middleware.py
- app/services/ai/runtime/agentscope/context_breakdown.py
- tests/services/ai/test_model_call_token_budget.py

**实施步骤：**

- [ ] 为一次模型调用建立局部 TokenCountResult，同时保存总 token、system token、tools token 和可用于 completion clamp 的输入 token。
- [ ] 让 estimate_context_breakdown 与 _clamp_completion_to_context 复用同一轮计数结果，避免同一组 messages/tools 重复调用 current_model.count_tokens。
- [ ] 只在一次模型调用或一次明确的工具循环轮次内做 memoization；不得建立无界的跨请求 prompt 缓存，避免消息可变、模型 tokenizer 变化和敏感内容驻留问题。
- [ ] 如果某个模型不支持可靠的 system/tools 拆分，使用已有精确 count_tokens 作为最终 guard，并采用保守的 fallback breakdown；禁止为了省一次计数而移除上下文上限保护。
- [ ] 覆盖短 prompt、长历史、工具 schema 很大、completion 被截断、计数接口异常和 messages 在调用前发生变化等测试。

**收益：** 当前 middleware 和 context_breakdown 可能对同一模型请求执行多次 token 统计；合并后可降低长 prompt/大工具 schema 场景的 CPU、远程 tokenizer 或模型适配器开销，直接改善模型调用前延迟。

**代价与风险：** token 计数结果如果和最终发送给模型的 messages/tools 不一致，会错误估计上下文剩余空间；模型适配器差异、缓存键设计和消息可变性都需要测试。最终 context guard 必须保留。

## 阶段五：工作区冷启动并发合并

**目标文件：**

- app/services/ai/runtime/agentscope/workspace.py
- app/services/ai/runners/assistant_agent_runner.py
- tests/services/ai/test_workspace_initialization.py

**实施步骤：**

- [ ] 先记录 get_local_workspace 的 cache hit/miss、root 解析、技能路径发现、sandbox policy 读取、Docker/E2B/SSH 获取、session skill preseed 和 initialize 的分段耗时。
- [ ] 对同一安全缓存键的并发冷启动增加 singleflight：第一个请求执行初始化，其他请求复用已完成结果或等待同一个 future。缓存键必须包含用户/工作目录/沙箱策略/技能来源等隔离因素。
- [ ] 对等待方和初始化方都设计取消处理；初始化失败时清理已创建资源并让下一请求可以重试，不能把失败 future 永久缓存。
- [ ] 只在已证明安全、生命周期可控的本地工作区考虑预热；不盲目预创建 Docker、E2B 或 SSH 资源，也不跨用户复用工作区。
- [ ] 保留现有路径授权、只读策略、资源清理和 Docker idle reaper 行为。

**收益：** 多个并发请求同时遇到同一个冷工作区时，可以避免重复初始化和重复资源获取，降低冷启动 TTFT。

**代价与风险：** singleflight 可能把多个请求集中阻塞在同一把锁/future 上；取消、初始化失败和容器泄漏处理复杂；如果缓存键过宽，会造成跨用户数据或权限边界问题。

## 阶段六：将多轮工具/数据修复纳入请求级预算

**目标文件：**

- app/services/ai/runners/assistant_agent_runner.py
- app/services/ai/runners/chatbi/native_turn.py
- app/services/ai/runners/chatbi/repair_controller.py
- app/services/ai/executors/federated_executor.py
- tests/ai/runners/test_execution_budget.py
- tests/ai/executors/test_federated_execution_budget.py

**实施步骤：**

- [ ] 增加请求级 ExecutionBudget，至少包括 deadline、剩余模型调用次数、剩余工具调用次数和已消耗时间；每次模型/工具/修复前检查并记录原因。

建议的结构如下：

~~~python
@dataclass
class ExecutionBudget:
    deadline: float
    max_model_calls: int
    max_tool_calls: int
    model_calls: int = 0
    tool_calls: int = 0

    def allow_model_call(self, now: float) -> bool:
        return now < self.deadline and self.model_calls < self.max_model_calls
~~~

- [ ] 将总预算与每类预算分开：普通 AgentScope 工具循环、ChatBI 数据修复、联邦执行计划修复仍保留各自的 correctness budget，但总预算不能被局部修复循环绕过。
- [ ] 只对已判定不可恢复的错误快速失败；可恢复的 SQL、schema、参数或数据源错误仍按现有 repair controller 处理。
- [ ] 达到预算时返回结构化、可观测的“预算耗尽/需要重试”状态和用户可理解的说明，不静默截断，也不把权限或 grounding 错误伪装成超时。
- [ ] 优先复用已有 SQL、数据集选择和中间结果，避免同一轮 follow-up 重新生成完全相同的查询；复用必须绑定请求和数据快照，不能跨用户共享。
- [ ] 测试普通工具循环、ChatBI repair、联邦执行、预算耗尽、模型超时和工具取消；确认 max depth=1、委派权限和 self-delegation 防护不变。

**收益：** 当前数据修复和联邦执行存在多轮模型调用上限，复杂异常可能形成很长的尾延迟。请求级总预算可以控制 P95/P99、token 成本和资源占用，且比直接全局降低修复轮数更容易解释和观测。

**代价与风险：** 预算过紧会让复杂查询更早失败、降低答案质量并增加用户重试；预算判断必须使用单调 deadline，且要区分模型慢、工具慢、数据源不可用和不可恢复业务错误。

## 阶段七：审计与流式收尾解耦，但保留持久化可靠性

**目标文件：**

- app/api/v1/endpoints/chat.py
- app/services/ai/agent_service.py
- app/services/ai/audit.py
- tests/api/v1/test_chat_stream_completion.py
- tests/services/ai/test_audit_lifecycle.py

**实施步骤：**

- [ ] 先确认当前客户端看到终端事件的时间与 _run_chat_turn_stream finally 中 AuditManager.log_transaction 完成时间之间的差值。
- [ ] 如果审计确实阻塞终端事件，将非关键的审计写入放入现有可靠后台队列或明确的 detached task；保留幂等键、失败重试和告警，不允许因为优化而丢失业务审计。
- [ ] 对 chat.py 当前 producer/consumer 队列增加有界性和明确的结束 sentinel 设计。客户端断开时允许必要的业务持久化继续，但要取消不再需要的网络发送和无界排队。
- [ ] 评估当前 250ms queue.get 轮询是否可以改为 queue 结束事件与断开事件的等待组合；任何改动都必须验证客户端断开、producer 异常、空流和正常 [DONE] 顺序。
- [ ] 不把审计失败吞掉；终端响应可以不等待低优先级审计，但审计失败必须进入可查询的失败路径。

**收益：** 如果当前总耗时主要在审计 DB 写入或队列轮询，能缩短用户看到完成信号的时间；有界队列还可以防止下游慢时内存无界增长。

**代价与风险：** 审计会从同步可靠路径变成最终一致；后台任务崩溃、进程退出和重试都可能造成审计延迟或丢失；队列结束和取消处理不当会造成 producer 泄漏或死锁。因此这项应在阶段一的测量确认后再做。

## 阶段八：分批验证与上线门槛

**实施步骤：**

- [ ] 每个阶段先写失败/边界测试，再实现代码；阶段一只加观测，不混入行为变化。
- [ ] 后端聚焦测试使用：

~~~bash
venv/bin/python -m pytest tests/services/ai/test_agent_latency_observability.py tests/services/ai/test_agent_execution_snapshot.py tests/services/ai/test_skill_resolver_cache.py tests/services/ai/test_model_call_token_budget.py -q --confcutdir=tests/ai
venv/bin/python -m pytest tests/ai/runners/test_execution_budget.py tests/ai/executors/test_federated_execution_budget.py -q --confcutdir=tests/ai
git diff --check
~~~

- [ ] 如果改动 frontend，再额外运行：

~~~bash
cd frontend && node_modules/.bin/vue-tsc --noEmit
~~~

- [ ] 在用户环境中按以下矩阵进行单请求与并发压测：冷/热工作区、自动/显式智能体、普通/知识库/数据查询、有/无技能、有/无工具、短/长历史、单并发/10 并发/50 并发、正常完成/模型超时/工具失败/客户端断开。
- [ ] 记录 p50/p95 TTFT、p50/p95 total、route/model/tool 次数、技能扫描次数、token count 次数、DB/Redis 往返、队列积压、审计完成率和错误分类。
- [ ] 接受标准：
  - 路由、权限、发布就绪、知识库 grounding、数据查询和委派边界测试无回归。
  - 正常完成、异常、取消、客户端断开均不丢必要历史和审计记录。
  - 优化后的目标阶段 p95 有明确下降；若只降低 CPU 但 TTFT/总耗时无改善，不宣称延迟优化成功。
  - 并发场景没有连接池耗尽、线程池排队恶化、工作区泄漏或无界队列增长。
  - 线上部署、服务重启和真实模型/数据源结果由用户在控制台验证后，才能报告为已上线效果。

## 推荐实施顺序

1. P0：阶段一观测基线。
2. P1：阶段二请求级 snapshot、阶段三技能元数据快照、阶段四 token 计数合并。这三项通常改动集中、收益可验证，且不会直接改变模型决策。
3. P2：阶段五工作区 singleflight、阶段六请求级多轮预算。两项对并发和长尾收益明显，但需要重点覆盖取消、资源清理和复杂查询质量。
4. P3：阶段七流式/审计解耦。只有观测证明审计或队列收尾占据明显耗时时才实施。

## 不建议直接采用的做法

- 不建议只把所有同步函数包进 asyncio.to_thread：它通常改善事件循环阻塞，不等于降低单请求延迟，并可能在线程池满时放大排队。
- 不建议用“启动时全量预热所有配置/技能/工作区”替代按需测量：会增加启动时间和内存，也可能跨用户或跨权限复用资源。
- 不建议把技能解析结果做成无 TTL、无失效的全局缓存。
- 不建议将记忆历史从精确范围读取改为先拉取完整窗口再截断；短 limit 场景会增加 Redis 网络和反序列化成本。
- 不建议直接把所有 repair rounds 全局调低；应该先做请求级总预算，并按错误类型保留可恢复修复。
- 不建议移除最终 token/context guard，或为了减少一次权限/就绪检查而复用过期的 agent 配置。
