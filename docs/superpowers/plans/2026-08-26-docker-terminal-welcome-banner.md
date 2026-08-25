# Docker Terminal Welcome Banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Docker 容器终端每次打开时显示结构化、彩色的中文欢迎信息，准确说明 `/workspace` 同步、运行资源、只读文档、临时数据和生命周期边界。

**Architecture:** 仅在 `DockerTerminalModal.vue` 内增加一个结构化 welcome record 和独立渲染分支；普通命令记录、Docker exec API、容器挂载和生命周期代码保持不变。欢迎卡从现有 `containerId` 与 `currentWorkdir` 读取动态信息，不暴露宿主机真实路径。

**Tech Stack:** Vue 3 `<script setup>`、TypeScript、Tailwind CSS、pytest 前端契约测试、`vue-tsc`。

---

### Task 1: 为欢迎卡和每次打开行为增加失败契约测试

**Files:**
- Modify: `tests/frontend/test_chat_sandbox_workspace_contract.py`，在 `test_docker_terminal_modal_component_contract` 后增加欢迎卡契约测试
- Test: `tests/frontend/test_chat_sandbox_workspace_contract.py`

- [x] **Step 1: Write the failing test**

在现有测试文件中新增：

```python
def test_docker_terminal_modal_renders_structured_welcome_card_each_open():
    terminal_modal = ROOT / "frontend/src/components/chat/DockerTerminalModal.vue"
    source = terminal_modal.read_text(encoding="utf-8")

    assert 'type WelcomeRecordKind = "command" | "welcome"' in source
    assert "const createWelcomeRecord = ()" in source
    assert 'kind: "welcome"' in source
    assert "records.value.push(createWelcomeRecord())" in source
    assert "immediate: true" in source
    assert "v-if=\"rec.kind === 'welcome'\"" in source
    assert "文件与同步" in source
    assert "/workspace/skills" in source
    assert "/workspace/public/docs" in source
    assert "同步到宿主机用户工作区" in source
    assert "停止 / 空闲回收" in source
    assert "重启 / 销毁" in source
    assert "能力越大，责任越大" in source
    assert "text-emerald-" in source
    assert "text-sky-" in source
    assert "text-violet-" in source
    assert "text-amber-" in source
    assert "text-rose-" in source


def test_docker_terminal_modal_keeps_command_execution_contract():
    terminal_modal = ROOT / "frontend/src/components/chat/DockerTerminalModal.vue"
    source = terminal_modal.read_text(encoding="utf-8")

    assert "/api/v1/sandbox/docker/workspace/exec" in source
    assert "runCommand" in source
    assert "clearTerminal" in source
    assert "commandHistory" in source
    assert "QUICK_COMMANDS" in source
```

- [x] **Step 2: Run the focused test to verify it fails**

Run:

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_chat_sandbox_workspace_contract.py -k "docker_terminal_modal" -q
```

Expected: the existing execution contract passes, while the new structured welcome-card test fails because the component has no welcome record type, no `createWelcomeRecord`, no independent welcome template, and no lifecycle text yet.

### Task 2: Implement the structured welcome record and rendering branch

**Files:**
- Modify: `frontend/src/components/chat/DockerTerminalModal.vue`

- [x] **Step 1: Add the record kind and welcome factory**

Add the following types and factory near `CommandRecord`:

```ts
type WelcomeRecordKind = "command" | "welcome";

interface CommandRecord {
  id: string;
  kind?: WelcomeRecordKind;
  command: string;
  workdir: string;
  stdout: string;
  stderr: string;
  output: string;
  exitCode: number;
  durationMs: number;
  timestamp: string;
  loading?: boolean;
}
```

Add a `createWelcomeRecord` function after `shortContainerId`:

```ts
const createWelcomeRecord = (): CommandRecord => {
  const workdir = currentWorkdir.value || "/workspace";
  const output = `Docker 沙箱终端\n已连接 容器：${props.containerId || "default"}\n工作目录：${workdir}`;
  return {
    id: `welcome_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    kind: "welcome",
    command: "nanzi-welcome",
    workdir,
    stdout: "",
    stderr: "",
    output,
    exitCode: 0,
    durationMs: 0,
    timestamp: new Date().toLocaleTimeString(),
  };
};
```

The text fields remain populated for the existing `CommandRecord` shape and copy behavior, while the `kind` field selects the structured template.

- [x] **Step 2: Make every visible transition append one welcome record**

Replace the current `records.value.length === 0` guard and inline welcome object in the `show` watcher with:

```ts
watch(
  () => props.show,
  (val) => {
    if (val) {
      records.value.push(createWelcomeRecord());
      focusInput();
      void scrollToBottom();
    }
  },
  { immediate: true },
);
```

This covers a modal mounted with `show=true` and later false-to-true opens. `clearTerminal()` remains unchanged, so clearing does not reinsert the card until the next open.

- [x] **Step 3: Render the welcome record as colored structured DOM**

Inside the existing `v-for`, render this branch before the normal command header:

```vue
<div
  v-if="rec.kind === 'welcome'"
  class="rounded-lg border border-slate-700/80 bg-slate-900/70 p-3 text-[11px] leading-relaxed"
>
  <div class="mb-2 flex items-center gap-2 text-emerald-300">
    <CommandLineIcon class="h-4 w-4" />
    <span class="font-semibold">Docker 沙箱终端</span>
    <span class="text-slate-500">· 环境说明</span>
  </div>
  <div class="grid gap-1 sm:grid-cols-2">
    <div><span class="text-emerald-300">● 已连接</span><span class="text-slate-400"> 容器：</span><span class="text-slate-100">{{ shortContainerId }}</span></div>
    <div><span class="text-sky-300">工作目录</span><span class="text-slate-400">：</span><span class="text-sky-200">{{ rec.workdir || '/workspace' }}</span></div>
  </div>
  <div class="mt-3 border-t border-slate-700/70 pt-2">
    <div class="mb-1 font-semibold text-slate-200">文件与同步</div>
    <div><span class="text-emerald-300">✓ 可写 / 会保留</span><span class="text-slate-400">　/workspace</span></div>
    <div class="pl-4 text-slate-400">这里的代码和文件会同步到宿主机用户工作区</div>
    <div class="mt-1"><span class="text-violet-300">◆ 运行资源</span><span class="text-slate-400">　/workspace/skills</span></div>
    <div class="pl-4 text-slate-400">平台技能运行快照，不建议手动修改</div>
    <div class="mt-1"><span class="text-slate-300">🔒 只读</span><span class="text-slate-400">　/workspace/public/docs</span></div>
    <div class="pl-4 text-slate-400">平台公共文档，只能读取</div>
    <div class="mt-1"><span class="text-rose-300">× 临时内容</span><span class="text-slate-400">　/tmp、运行中的进程、非挂载路径文件</span></div>
    <div class="pl-4 text-slate-400">容器停止、回收或重建后不保证保留</div>
  </div>
  <div class="mt-3 border-t border-slate-700/70 pt-2 text-amber-200">
    <div class="font-semibold">生命周期</div>
    <div class="text-slate-300">停止 / 空闲回收：释放容器资源，<span class="text-emerald-300">/workspace 文件保留</span></div>
    <div class="text-slate-300">重启 / 销毁：删除旧容器，<span class="text-emerald-300">/workspace 文件保留</span>；临时进程和容器内临时数据消失</div>
  </div>
  <div class="mt-3 rounded-md border border-rose-500/30 bg-rose-950/20 p-2 text-rose-200">
    <div class="font-semibold">⚠ 安全提示</div>
    <div class="text-rose-200/80">能力越大，责任越大。删除文件、安装依赖、联网或启动后台进程前，请先确认路径和影响范围。</div>
  </div>
</div>
```

Wrap the current command header, loading state, and output block in a `<template v-else>` immediately after this new branch, leaving their contents unchanged. Do not change the request payload, endpoint, or command history logic.

- [x] **Step 4: Run the focused test and type check**

Run:

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_chat_sandbox_workspace_contract.py -k "docker_terminal_modal" -q
cd frontend && npm exec -- vue-tsc --noEmit
```

Expected: both focused contract tests pass and `vue-tsc` exits with code 0 or reports only pre-existing repository errors, which must be recorded separately.

### Task 3: Review the diff and verify the existing terminal behavior

**Files:**
- Inspect: `frontend/src/components/chat/DockerTerminalModal.vue`
- Inspect: `tests/frontend/test_chat_sandbox_workspace_contract.py`
- Inspect: `docs/superpowers/specs/2026-08-26-docker-terminal-welcome-banner-design.md`

- [x] **Step 1: Run the complete relevant frontend contract file**

Run:

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_chat_sandbox_workspace_contract.py -q
```

Expected: all tests in this contract file pass.

- [x] **Step 2: Verify the changed files have no whitespace errors**

Run:

```bash
git diff --check -- frontend/src/components/chat/DockerTerminalModal.vue tests/frontend/test_chat_sandbox_workspace_contract.py
```

Expected: no output and exit code 0.

- [x] **Step 3: Inspect the final diff for scope and behavior**

Run:

```bash
git diff -- frontend/src/components/chat/DockerTerminalModal.vue tests/frontend/test_chat_sandbox_workspace_contract.py
git status --short
```

Confirm that no existing user edits outside the owned files were changed, no Docker API/backend files were modified, and no service/deployment script was run. Git staging and committing remain user-controlled and are intentionally not part of this execution.
