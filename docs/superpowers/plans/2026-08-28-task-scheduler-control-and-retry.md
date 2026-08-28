# 任务调度器节点开关与失败重试实施计划

> **For agentic workers:** 按测试先行执行本计划，保持无关工作区改动；本任务不自动提交、不运行服务或部署脚本。

**目标：** 支持通过 `TASK_SCHEDULER_ENABLED` 控制当前节点是否启动调度器，并在智能体定时任务编辑页暴露已有的失败重试配置。

**架构：** 使用现有 FastAPI lifespan 和 APScheduler 启动入口增加节点级 gate；使用现有 `AgentScheduledTask.config` 持久化 `max_retries`/`retry_delay_seconds`，前端只在智能体任务编辑弹窗中读写并做范围约束。

**技术栈：** Python 3.11、Pydantic Settings、FastAPI lifespan、Vue 3 + TypeScript、pytest。

## 1. 锁定失败测试

**Files:**

- Create: `tests/core/test_task_scheduler_settings.py`
- Create: `tests/frontend/test_task_scheduler_control_contract.py`
- Create: `tests/services/test_scheduler_reconcile_contract.py`

- 测试 `TASK_SCHEDULER_ENABLED` 默认开启，并可解析为关闭。
- 测试 lifespan 使用该开关包住 scheduler 启动调用，并记录关闭日志。
- 测试任务中心存在重试状态、从 `config.max_retries`/`config.retry_delay_seconds` 回填、保存时写回两个字段，并展示定时触发/立即执行边界说明。
- 测试开启节点注册共享任务库对账任务，并清理已不存在的任务/报告订阅 job。
- 先运行聚焦测试，确认在生产代码尚未修改时失败。

## 2. 实现节点级调度器 gate

**Files:**

- Modify: `app/core/config.py`
- Modify: `app/main.py`
- Modify: `app/services/ai/scheduler_service.py`

- 在 Settings 中新增 `TASK_SCHEDULER_ENABLED: bool = True`。
- 在 lifespan 启动阶段仅当该值为真时调用 `scheduler_service.start()`；关闭时输出明确日志。
- 保留 shutdown 的 `stop()` 调用，因为服务本身已对未启动 scheduler 做安全空操作。
- 开启节点增加 30 秒一次的任务库对账，清理已停用/删除的旧 job，并同步关闭节点提交的任务和报告订阅变更。
- 不改变现有任务执行锁和重试持久化逻辑。

## 3. 将重试策略接入任务编辑页

**Files:**

- Modify: `frontend/src/views/TaskCenter.vue`

- 增加最大重试次数和重试间隔（分钟）状态，并在新建/编辑时从现有 config 初始化。
- 保存时将最大次数规范到 `0–3`，将间隔规范到 `1–60` 分钟后转换到 `retry_delay_seconds`。
- 在编辑弹窗加入“执行失败策略”区块，清楚说明仅定时触发有效、手动立即执行不自动重试、默认不重试。
- 不改报告订阅设置页和后端报告订阅执行逻辑。

## 4. 回归验证

**Files:**

- Verify: 新增 Settings/frontend 契约测试
- Verify: `tests/frontend/test_task_center_notification_contract.py`
- Verify: `tests/frontend/test_task_prompt_composer_contract.py`
- Verify: `tests/services/test_scheduler_service.py` 中重试策略相关测试

- 运行新增测试和关联前端契约测试。
- 运行 `vue-tsc --noEmit` 做前端类型检查。
- 运行变更范围 `git diff --check`，检查最终 diff/status。
- 汇报真实多节点部署、数据库/Redis、浏览器手工验收仍未由代理执行。
