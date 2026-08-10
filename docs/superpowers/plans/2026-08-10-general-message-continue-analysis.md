# 通用消息继续分析快捷指令实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在通用智能体的 AI 消息下增加“继续分析”快捷菜单，点击后只发送自然语言指令；ChatBI 消息继续使用已有的 ChatBI 专属菜单。

**Architecture:** 新增一个无业务副作用的 Vue 快捷菜单组件，内部只维护固定的 `label/query` 列表，通过 `select(query)` 事件交给现有 `handleQuickQuestion()` 发送。通用消息展示该组件时要求 SSE 携带的 `agent_type` 为 `GENERAL`，并排除已有 `chatbiInsight` 的消息，避免知识库、ChatBI 和其他专用消息误显示；点击时将被选中的 AI 回复作为隐藏上下文一并发送。四个快捷指令包含可视化分析、Markdown、Word 和 Skill；其中 Skill 指令明确要求直接调用现有 `create_skills` 工具并使用 `scope=personal`。

**Tech Stack:** Vue 3 Composition API、TypeScript、Tailwind CSS、pytest 前端源码契约测试。

---

### Task 1: 建立通用快捷菜单契约

**Files:**
- Create: `frontend/src/components/chat/MessageContinueAnalysis.vue`
- Test: `tests/frontend/test_general_message_continue_analysis_contract.py`

- [x] **Step 1: Write the failing contract test**

  Assert that the component defines the four supported labels, emits a selected query instead of a local action, includes the complete Markdown/Word/visualization instructions, explicitly names `create_skills`, uses `scope=personal`, requires real tool execution, and supports mobile/desktop chooser rendering.

- [x] **Step 2: Run the focused test and verify it fails**

  Run `venv/bin/python -m pytest tests/frontend/test_general_message_continue_analysis_contract.py -q`.

  Expected: collection succeeds and the contract fails because the component does not yet exist.

- [x] **Step 3: Implement the minimal component**

  Use the existing `ChatBIContinueAnalysis.vue` interaction pattern: one trigger button named “继续分析”, a mobile bottom sheet, a desktop popover, close-on-pointer/focus/Escape behavior, and a single `select` event carrying the selected query. Define four queries: visual ECharts report, Markdown document to the workspace `docs` directory, Word document via the existing tool with its actual download address, and the `create_skills` personal Skill instruction.

  ```ts
  const actions = [
    {
      id: "save_markdown",
      label: "保存为 Markdown",
      description: "保存到我的 doc 目录并返回实际路径",
      query: "请将刚才这条 AI 回复完整保存为 Markdown 文档，文件名根据内容自动生成，保存到我的 doc 目录下。保存完成后请返回实际写入的完整路径，并确认文件已经成功保存。不要只给我建议路径或示例路径。",
    },
    {
      id: "save_word",
      label: "保存为 Word",
      description: "生成 .docx 文件并返回实际路径",
      query: "请将刚才这条 AI 回复整理并保存为 Word 文档（.docx），文件名根据内容自动生成，保存到我的 doc 目录下。保存完成后请返回实际生成文件的完整路径，并确认文件已经成功生成。",
    },
    {
      id: "create_skill",
      label: "提炼生成 Skill",
      description: "按 create_skills 工具规范生成个人 Skill",
      query: "请根据刚才这条 AI 回复的内容，直接调用 create_skills 工具提炼并创建一个个人 Skill。请按照工具要求生成合法的 skill_id、名称、用途描述和完整的 SKILL.md 内容：文件必须以包含 name 和 description 的 YAML Frontmatter 开始，后续使用清晰、可执行的 imperative 指令。scope 使用 personal。不要只输出 Skill 草稿，必须实际调用工具创建。创建成功后请返回 Skill 名称、skill_id、作用域和工具返回的完整物理路径，并说明如何使用。",
    },
  ];
  ```

- [x] **Step 4: Run the focused test and verify it passes**

  Run `venv/bin/python -m pytest tests/frontend/test_general_message_continue_analysis_contract.py -q`.

  Expected: PASS.

### Task 2: Wire the menu into both chat surfaces

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/frontend/test_general_message_continue_analysis_contract.py`

- [x] **Step 1: Extend the failing contract**

  Assert both views import and render `MessageContinueAnalysis`, pass the existing mobile state, send through `handleQuickQuestion` with the clicked message content, and render it only for `GENERAL` agent messages that are not thinking and do not have ChatBI insight actions.

- [x] **Step 2: Run the focused test and verify the new assertions fail**

  Run `venv/bin/python -m pytest tests/frontend/test_general_message_continue_analysis_contract.py -q`.

  Expected: the component assertions pass, while both-view wiring assertions fail.

- [x] **Step 3: Add the minimal view wiring**

  Add `agent_type` to the resolved `ChatConfig` and SSE meta event, then import the component in both views. Place it beside the existing message footer actions with this behavior:

  ```vue
  <MessageContinueAnalysis
    v-if="msg.role === 'agent' && msg.agentType === 'GENERAL' && !msg.chatbiInsight?.actions?.length && !msg.isThinking && msg.content"
    :is-mobile="isMobile"
    @select="(query) => handleQuickQuestion(query, 'send', msg.content)"
  />
  ```

  In `EmbedChat.vue`, retain the existing `checkRole(msg, 'agent')` convention instead of duplicating role checks.

- [x] **Step 4: Run the focused contract and related frontend contracts**

  Run `venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_general_message_continue_analysis_contract.py tests/frontend/test_chatbi_insight_contract.py -q`.

  Expected: all selected tests pass; ChatBI wiring remains unchanged.

### Task 3: Static/type verification and scope review

**Files:**
- Modify: `tests/CHECKLIST.md` only if the repository's current workflow requires recording this feature; otherwise do not touch it.

- [x] **Step 1: Run source and syntax checks**

  Run `venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_general_message_continue_analysis_contract.py tests/frontend/test_chatbi_insight_contract.py tests/frontend/test_personal_skills_experience_contract.py -q`.

- [x] **Step 2: Run `git diff --check`**

  Expected: no whitespace errors in the scoped changes.

- [x] **Step 3: Review the diff**

  Confirm there is no new backend action endpoint, no direct file write from the frontend, no automatic Skill publication, no change to ChatBI actions, selected-message context is preserved, and no staging or commit performed.
