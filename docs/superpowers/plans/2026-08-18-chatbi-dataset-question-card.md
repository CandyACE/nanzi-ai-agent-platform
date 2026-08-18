# ChatBI 数据集歧义提问卡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 当管理员未绑定数据集且 Schema 检索命中多个高置信度数据集时，复用现有 `ask_user_question` 渲染数据集选择卡；用户选择后把经过服务端校验的 ID 带入下一轮 Schema/SQL 执行，避免泛化提示后停住。

**Architecture:** Schema 格式化块携带 `metadata_dataset_id`，歧义检测按数据集而不是物理表分组，并把候选保存到 ChatBI 回合状态。Repair policy 在有候选时强制选择 `ask_user_question`；提问事件持久化一个受控 `purpose`，恢复回执后仅对该 purpose 提取已校验的数字数据集 ID，覆盖当前回合的 `metadata_dataset_ids`。

**Tech Stack:** Python 3.11、Pydantic 2、AgentScope `ToolChoice`、pytest、Vue 现有 UserQuestionCard/SSE 协议。

---

### Task 1: Schema 候选身份与歧义判定

**Files:**
- Modify: `app/services/schema_chunk_format.py`
- Modify: `app/services/chatbi_dataset_schema_service.py`
- Modify: `app/services/ai/runners/chatbi/run_state.py`
- Modify: `app/services/ai/runners/chatbi/tool_result_handlers.py`
- Test: `tests/services/test_schema_chunk_format.py`
- Test: `tests/ai/runners/test_data_agent_runner.py`

- [ ] **Step 1: Write the failing tests**

  增加带 `metadata_dataset_id` 的 Schema 块断言、同一数据集多张表不再歧义、多个数据集能够提取两个带数字 ID 的选择候选，并断言候选被保存到 `DataRunState.schema_ambiguity_candidates`。

- [ ] **Step 2: Run focused tests to verify failure**

  Run: `pytest -q tests/services/test_schema_chunk_format.py tests/ai/runners/test_data_agent_runner.py -k 'schema_ambiguity or schema_candidates or format_schema'`

  Expected: FAIL，因为当前格式化结果丢失数据集 ID，且歧义检测按 `dataset.table` 判断。

- [ ] **Step 3: Implement the minimal schema metadata changes**

  `format_schema_chunk()` 新增可选 `dataset_id`，在 header 中追加 `dataset_id=<id>`；`format_schema_hits()` 从 `metadata_dataset_id`/`dataset_id`/`rag_dataset_id` 传递该值。RAG/local/fallback/cross-dataset 四条生成路径都保留来源 ID。新增候选提取函数，按数据集 ID 优先、名称次之分组；仅将高置信度且分数接近的不同数据集生成 `{id,label,description}` 候选。`detect_schema_ambiguity()` 同样按数据集身份分组，避免同一数据集多表触发澄清。回合状态保存候选，并在每次 Schema 结果开始时清空旧候选。

- [ ] **Step 4: Run the focused tests**

  Run the command from Step 2; Expected: PASS。

### Task 2: 强制调用现有 ask_user_question

**Files:**
- Modify: `app/services/ai/runners/chatbi/repair_policy.py`
- Modify: `app/services/ai/tools/user_question_tools.py`
- Modify: `app/services/ai/user_question.py`
- Test: `tests/ai/runners/test_data_agent_runner.py`
- Test: `tests/ai/tools/test_user_question_tool.py`

- [ ] **Step 1: Write the failing tests**

  对带两个数据集候选的状态断言 repair tool choice 为 `ToolChoice(mode="ask_user_question")`，repair message 包含候选 ID 和 `purpose=chatbi_dataset_selection`；对工具输出、SSE、持久化事件断言 purpose 会被保留。

- [ ] **Step 2: Run focused tests to verify failure**

  Run: `pytest -q tests/ai/runners/test_data_agent_runner.py tests/ai/tools/test_user_question_tool.py -k 'schema_ambiguous or user_question or purpose'`

  Expected: FAIL，因为当前歧义分支返回 `None`，工具协议没有 purpose 字段。

- [ ] **Step 3: Implement the forced question card**

  `AskUserQuestionArgs` 增加可选 `purpose` 并原样进入工具 JSON、SSE 和持久化 payload。repair policy 根据状态候选构造单选数据集选项，禁用自定义输入，并返回 `ToolChoice(mode="ask_user_question")`；无结构化候选时保持原有兜底行为。

- [ ] **Step 4: Run the focused tests**

  Run the command from Step 2; Expected: PASS。

### Task 3: 用户选择后的受控恢复

**Files:**
- Modify: `app/services/ai/user_question.py`
- Modify: `app/services/ai/agent_service.py`
- Test: `tests/ai/tools/test_user_question_tool.py`
- Test: `tests/ai/test_user_question_store.py`

- [ ] **Step 1: Write the failing test**

  增加纯函数回归测试：只有 `purpose=chatbi_dataset_selection` 且选项经过服务端记录校验时，才返回数字数据集 ID；普通问题、取消回答、非数字 ID 都不能改变数据集范围。

- [ ] **Step 2: Run the focused test to verify failure**

  Run: `pytest -q tests/ai/tools/test_user_question_tool.py tests/ai/test_user_question_store.py -k 'dataset_selection or metadata_dataset'`

  Expected: FAIL，因为当前 agent service 忽略 `submit_answer()` 返回记录。

- [ ] **Step 3: Implement resume scope injection**

  `chat_completion_stream()` 保存 `submit_answer()` 返回记录，调用受控解析函数；命中 purpose 且存在合法选项 ID 时覆盖当前调用的 `metadata_dataset_ids`，再进入已有内部执行链。取消、普通提问和异常仍按现有逻辑处理，不从客户端 receipt 直接信任数据集 ID。

- [ ] **Step 4: Run the focused tests**

  Run the command from Step 2; Expected: PASS。

### Task 4: 全量回归与差异检查

**Files:**
- Test only: existing focused/backend/frontend contract suites

- [ ] **Step 1: Run all directly affected tests**

  Run: `pytest -q tests/services/test_schema_chunk_format.py tests/ai/runners/test_data_agent_runner.py tests/ai/tools/test_user_question_tool.py tests/ai/test_user_question_store.py tests/frontend/test_user_question_contract.py`

- [ ] **Step 2: Run static diff checks**

  Run: `git diff --check` and inspect `git diff --stat` plus the scoped diff; ensure no browser-related edits were changed.

- [ ] **Step 3: Report handoff**

  汇报根因、修改文件、测试结果和未执行的服务启动/部署动作；不自动 stage/commit，除非用户另行要求。
