# 模型默认思考模式语义调整 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `thinking_only` 只决定后端默认思考状态，并让前端会话级思考覆盖独立于该字段。

**Architecture:** 保留现有数据库/API 字段名。后端解析器以 `thinking_enable` 表示能力，以 `thinking_only` 计算无覆盖时的默认值；显式会话覆盖只校验能力和 `allow_disable_thinking`。前端按同一规则初始化开关，关闭权限只在当前已开启时由 `allow_disable_thinking` 控制。

**Tech Stack:** Python 3.11、pytest、Vue 3、TypeScript、前端契约测试。

---

### Task 1: 锁定后端默认与会话覆盖语义

**Files:**
- Modify: `tests/ai/runtime/test_reasoning_request_config.py`
- Modify: `app/services/ai/reasoning.py`

- [x] **Step 1: Write the failing tests**

在 `tests/ai/runtime/test_reasoning_request_config.py` 增加解析器测试，断言：

```python
def test_reasoning_defaults_to_thinking_only_for_registered_model():
    from app.services.ai.reasoning import resolve_reasoning_settings

    assert resolve_reasoning_settings(
        thinking_enable=True,
        thinking_only=True,
        reasoning_effort="high",
    ).thinking_enable is True
    assert resolve_reasoning_settings(
        thinking_enable=True,
        thinking_only=False,
        reasoning_effort="high",
    ).thinking_enable is False


def test_explicit_session_thinking_override_ignores_thinking_only():
    from app.services.ai.reasoning import resolve_reasoning_settings

    assert resolve_reasoning_settings(
        thinking_enable=True,
        thinking_only=False,
        reasoning_effort="high",
        overrides={"thinking_enable": True},
    ).thinking_enable is True
    assert resolve_reasoning_settings(
        thinking_enable=True,
        thinking_only=True,
        reasoning_effort="high",
        allow_disable_thinking=True,
        overrides={"thinking_enable": False},
    ).thinking_enable is False


def test_explicit_disable_only_requires_allow_disable_thinking():
    from app.services.ai.reasoning import resolve_reasoning_settings

    result = resolve_reasoning_settings(
        thinking_enable=True,
        thinking_only=True,
        reasoning_effort="high",
        allow_disable_thinking=False,
        overrides={"thinking_enable": False},
    )

    assert result.thinking_enable is True
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/ai/runtime/test_reasoning_request_config.py -k "default or explicit_session or explicit_disable" -q
```

Expected: the default-off and explicit-override cases fail against the current `thinking_only`-based disable logic.

- [x] **Step 3: Implement the minimal resolver change**

Initialize the effective state with the registered default:

```python
effective_thinking = bool(thinking_enable and thinking_only)
```

Then make explicit overrides use model capability and `allow_disable_thinking`:

```python
if requested_thinking:
    if thinking_enable:
        effective_thinking = True
    else:
        logger.warning("Ignoring thinking_enable=true for a non-thinking model")
elif effective_thinking and allow_disable_thinking:
    effective_thinking = False
elif effective_thinking:
    logger.warning("Ignoring unauthorized thinking disable request")
```

- [x] **Step 4: Run the focused backend tests**

Run the same pytest command and expect all selected tests to pass.

### Task 2: Align frontend session state and permission contract

**Files:**
- Modify: `frontend/src/components/embed/ChatInput.vue`
- Modify: `frontend/src/components/task/TaskPromptComposer.vue`
- Modify: `frontend/src/components/system/ModelRegistry.vue`
- Modify: `tests/frontend/test_model_thinking_config_contract.py`

- [x] **Step 1: Add contract assertions for the new frontend semantics**

Assert that the components compute the default session state from both fields, allow enabling a capable model, and that disable permission does not require `!thinking_only`:

```python
def test_chat_input_uses_thinking_only_for_default_state_only():
    source = CHAT_INPUT.read_text(encoding="utf-8")

    assert "props.thinkingEnableOverride ?? Boolean(selectedModelConfig.value.thinking_only)" in source
    assert "&& selectedModelConfig.value.allow_disable_thinking" in source
    assert "&& !selectedModelConfig.value.thinking_only" not in source
```

- [x] **Step 2: Run the frontend contract test to verify it fails**

Run:

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/frontend/test_model_thinking_config_contract.py -k "default_state_only" -q
```

Expected: FAIL because the current component defaults to `true` and couples disable permission to `thinking_only`.

- [x] **Step 3: Implement the minimal frontend change**

Use the model's `thinking_only` value as the fallback session state while retaining explicit overrides. Allow toggling whenever the model is capable and either the current state is off or disabling is permitted:

```ts
const thinkingEnabledForSession = computed(() => {
  if (!selectedModelConfig.value?.thinking_enable) return false;
  return props.thinkingEnableOverride ?? Boolean(selectedModelConfig.value.thinking_only);
});

const canToggleThinking = computed(() => Boolean(
  selectedModelConfig.value?.thinking_enable
  && (!thinkingEnabledForSession.value || selectedModelConfig.value.allow_disable_thinking),
));
```

Apply the same state and toggle rules in `TaskPromptComposer.vue`. Update `ModelRegistry.vue` labels to “默认思考模式” and “模型默认以思考模式运行”。

- [x] **Step 4: Run the focused frontend contract tests**

Run the full `tests/frontend/test_model_thinking_config_contract.py` file and expect it to pass.

### Task 3: Validate the complete reasoning configuration surface

**Files:**
- No additional files.

- [x] **Step 1: Run the focused backend reasoning suite**

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/ai/runtime/test_reasoning_request_config.py -q
```

- [x] **Step 2: Run the model configuration contract suite**

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/test_model_thinking_schema_contract.py tests/frontend/test_model_thinking_config_contract.py -q
```

- [x] **Step 3: Inspect the final diff and whitespace**

```bash
git diff --check -- app/services/ai/reasoning.py frontend/src/components/embed/ChatInput.vue tests/ai/runtime/test_reasoning_request_config.py tests/frontend/test_model_thinking_config_contract.py docs/superpowers/specs/2026-08-07-model-thinking-default-design.md docs/superpowers/plans/2026-08-07-model-thinking-default.md
git diff --stat
```

Do not stage or commit files.
