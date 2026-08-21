# 实现计划：Bash 环境探测与输入框风险横幅

> 设计文档：[2026-08-21-bash-environment-banner-design.md](../specs/2026-08-21-bash-environment-banner-design.md)
> 已获用户批准（"开发吧"）。本文档把设计落实为可分步执行的实现计划。

## 目标（延续设计）

- 一轮对话内**首个** Bash 工具调用时，在输入框上方的 banner 区弹出一条环境提示。
- container = 绿色"Bash 运行在容器沙箱，环境安全"；host = 琥珀黄风险文案。
- 同轮后续 bash 不重复触发；流结束自动关闭；手动 × 仅清当前本轮，下轮重触发；探测失败静默降级 host。
- 零额外 HTTP 请求：探测结果经由现有 SSE 事件内嵌下发（方案 A）。

## 关键约束（已在探索中证实）

- 后端无 Pinia、无 `stores/` 目录。banner 状态必须放在 **EmbedChat.vue 组件级 `ref`**，经 `ChatInput` 的 banner slot 传入。
- `ChatInput` 的 `<template #banner>` 当前渲染 `ChatTodoCard`（`activeTodoTimeline`）。banner 需与 TodoCard **共存**（两者可能同时为真）。
- 不新建后端 HTTP 端点；不改 admin `system.py` / LTM 遗留。
- Python 3.11（禁 3.12+ 语法）；不运行 `./dev.sh`/部署；改造后提醒用户在控制台自行 `./dev.sh`。
- 工作区已有**不相关**的未提交改动（其它功能），本实现只触碰涉及文件，避免误提交他人改动。

---

## 步骤 1：新增后端探测函数（新文件）

**文件**：`app/utils/env.py`（新建）

模块级缓存常量 + 纯函数，供事件流与测试复用：

```python
"""运行环境探测：判断当前后端进程跑在容器(Docker/k8s Pod)还是宿主机。"""
from __future__ import annotations

import os
from typing import Literal

EnvKind = Literal["docker", "host"]

# 进程级恒定，模块首次调用时缓存一次
_cache: EnvKind | None = None

[docker_markers] = ["/.dockerenv"]
[container_dirs] = ["/app"]
[cgroup_needles] = ["docker", "kubepods"]


def _has_cgroup_container_marker() -> bool:
    try:
        with open("/proc/self/cgroup", "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
    except OSError:
        return False
    return any(n in content for n in cgroup_needles)


def detect_env(raw: bool = False) -> EnvKind:
    """判定当前环境为容器还是宿主机。

    - 有 `/.dockerenv` 或 `/app` 目录或 cgroup 含 docker/kubepods → docker
    - 其余（含探测异常）→ host（静默降级，调用方负责 debug 日志）
    """
    has_dockerenv = os.path.exists("/.dockerenv")
    has_app_dir = os.path.exists("/app")
    has_cgroup = _has_cgroup_container_marker()
    if has_dockerenv or has_app_dir or has_cgroup:
        return "docker"
    return "host"


def get_env() -> EnvKind:
    global _cache
    if _cache is None:
        _cache = detect_env()
    return _cache
```

> 备注：`/app` 目录判断沿用 `config.py` 的 `SKILLS_DIR` 先例；`kubepods` 归 docker，避免把 k8s 误标为宿主机。raw 参数留给测试注入场景（可绕过缓存直接探测），若不需要可在实现时去掉。

## 步骤 2：SSE 事件流发射 bash_env（改现有文件）

**文件**：`app/services/ai/runtime/agentscope/event_stream.py`

1. 顶部导入：`from app.utils.env import get_env`（若路径不可达则按仓库实际约定调整 import）。
2. `new_native_stream_state()` 内新增去重标志（保持 setdefault 风格）：
   ```python
   state.setdefault("bash_env_emitted", False)
   ```
3. `map_standard_agentscope_event` 的 `TOOL_CALL_START` 分支（约 371-412 行），在现有 `yield {"type":"log","title":f"调用工具: {tool_name}"...}`（405-411）之后、`return`（412）之前插入：
   ```python
   # Bash 环境探测横幅：仅本轮首次 Bash 调用发射一次（方案 A，SSE 内嵌）
   if tool_name == "Bash" and not state.get("bash_env_emitted"):
       state["bash_env_emitted"] = True
       yield {
           "type": "bash_env",
           "env": get_env(),
       }
   ```
   - `tool_name == "Bash"` 是唯一入口（`bash`/`exec_command`/`Bash` 别名统一映射为 `"Bash"`，见 registry）。
   - `bash_env_emitted` 随 state 随会话流转，天然覆盖"整轮结束/下轮重置"语义（下轮新建 state → 再次触发）。

## 步骤 3：前端 SSE 分发新增 case（改现有文件）

**文件**：`frontend/src/utils/agentscopeSseHandlers.ts`

1. `dispatchAgentscopeStreamEvent` 的 switch 内新增类型化分支（放在 `tool_result_data` 附近，位置不敏感）：
   ```ts
   case "bash_env": {
     const env = (data as { env?: "host" | "docker" }).env ?? "host";
     onBashEnv(env);
     return true;
   }
   ```
2. 函数签名增加回调参数 `onBashEnv: (env: "host" | "docker") => void`（带默认 no-op，避免破坏 AgentDebug.vue 等其它调用点）。分发行 `return true` 表示已处理。

> 说明：`dispatchAgentscopeStreamEvent` 同时被 `EmbedChat.vue`、`AgentDebug.vue` 调用。全部在 switch 中统一解析事件；`onBashEnv` 只作"事件解析后的回调"，由各自调用点决定横幅落在哪。

## 步骤 4：EmbedChat.vue 横幅状态与渲染（改现有文件）

**文件**：`frontend/src/views/EmbedChat.vue`

1. 在 `isProcessing`（2736 行）附近新增状态：
   ```ts
   /** Bash 环境横幅：null 表示不显示；"host"|"docker" 表示本轮探测结果 */
   const bashBannerEnv = ref<"host" | "docker" | null>(null);
   const bashBannerDismissed = ref(false); // 手动 × 关闭当前轮
   const showBashBanner = computed(
     () => bashBannerEnv.value !== null && !bashBannerDismissed.value,
   );
   ```
2. 分发调用处（6800+ 行 `addEmbedLogFromStream` 回调附近的 `dispatchAgentscopeStreamEvent`）追加回调：
   ```ts
   dispatchAgentscopeStreamEvent(msg, data, addEmbedLogFromStream, messages.value, (env) => {
     bashBannerEnv.value = env;
     bashBannerDismissed.value = false; // 新轮探测重新允许显示（同轮重复 bash 不会再触发）
   })
   ```
   即把 banner 状态写入组件级 ref。
3. 流终态复位：在 `finally`（7483-7500 附近 `isProcessing.value = false` 处）追加：
   ```ts
   bashBannerEnv.value = null;
   bashBannerDismissed.value = false;
   ```
4. banner slot（1230-1232 附近）改为 TodoCard 与 bash 横幅共存：
   ```html
   <template #banner>
     <div v-if="activeTodoTimeline" class="mx-3 mt-2">
       <ChatTodoCard :timeline="activeTodoTimeline" />
     </div>
     <div v-if="showBashBanner" class="mx-3 mt-2">
       <BashEnvBanner
         :env="bashBannerEnv!"
         @dismiss="bashBannerDismissed = true"
       />
     </div>
   </template>
   ```
5. import `BashEnvBanner`。

## 步骤 5：新建前端横幅组件（新文件）

**文件**：`frontend/src/components/chat/BashEnvBanner.vue`（新建，先确认组件目录命名惯例 `components/chat`）

- `defineProps<{ env: "host" | "docker" }>()`，`defineEmits<{ dismiss: [] }>()`。
- 视觉：
  - `env === "docker"`：绿色（Tailwind `bg-emerald-50 border-emerald-200 text-emerald-800`）文案"🟢 Bash 运行在容器沙箱（`/app`），环境安全"。
  - `env === "host"`：琥珀黄（`bg-amber-50 border-amber-200 text-amber-800`）风险文案"⚠️ Bash 正在宿主机上执行，存在命令风险，建议 Docker 部署或改用 sandbox"。
- 右侧 × 按钮（`@click="$emit('dismiss')"`），圆角边框 + 图标布局，风格对齐现有 `ChatTodoCard`。

## 步骤 6：测试

- **后端单测**（新增 `tests/services/ai/test_env.py` 或合适目录）：
  - mock `/.dockerenv` 存在 → docker；
  - 无 dockerenv、`/proc/self/cgroup` 含 `docker` → docker；
  - 含 `kubepods` → docker（不误标 host）；
  - 三者皆无 → host；
  - 探测异常（`open` 抛 OSError）→ host。
- **前端契约测试**（新增到 `tests/frontend/`）：
  - `dispatchAgentscopeStreamEvent` 收到 `bash_env` → 调用 `onBashEnv("docker")` 且返回 true；
  - 收到未知/其它 type → 不调用且返回 false。
- **类型检查**：`vue-tsc --noEmit`。（Agent 不代跑，提醒用户在控制台执行。）

## 步骤 7：复核与交付

- 自审：确认 axios/无额外请求、host 文案含"宿主机/风险/Docker/沙箱"、container 文案含"容器沙箱"、"绿色/琥珀黄"如设计。
- 不触碰无关未提交改动；只新增/修改本功能文件。
- 提交（可选，若用户要求）；提醒用户在控制台自行 `./dev.sh` 验证。

---

## 变更文件清单

| 文件 | 类型 | 改动 |
|------|------|------|
| `app/utils/env.py` | 新增 | 探测函数 + 缓存 |
| `app/services/ai/runtime/agentscope/event_stream.py` | 修改 | state 标志 + TOOL_CALL_START 发射 bash_env |
| `frontend/src/utils/agentscopeSseHandlers.ts` | 修改 | switch 新增 case + `onBashEnv` 回调参数 |
| `frontend/src/views/EmbedChat.vue` | 修改 | 组件级 ref、分发回调、终态复位、banner slot |
| `frontend/src/components/chat/BashEnvBanner.vue` | 新增 | 横幅组件（deer 双色） |
| `tests/.../test_env.py` | 新增 | 探测单测 |
| `tests/frontend/*` | 新增 | 前端契约测试 |

## 风险与应对

- **`onBashEnv` 签名破坏其它调用点**：用默认 no-op 参数，AgentDebug.vue 等不受影响。
- **TodoCard 与横幅同时出现多层**：两者各自独立 `v-if`，DOM 中并列，互不干扰布局。
- **`get_env` 缓存与测试冲突**：测试直接调 `detect_env()`（不带缓存）或注入 `_cache` 重置，避免污染进程级缓存。
- **import 路径不确定**：按仓库既有 `from app...` 约定（见 config.py / event_stream.py 顶部），实现时核实。