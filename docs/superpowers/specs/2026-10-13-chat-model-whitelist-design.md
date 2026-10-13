# 聊天输入框模型白名单：按角色与用户限制「手动切换」的模型范围

- 日期：2026-10-13
- 状态：设计待评审
- 关联交付：版本级「允许在输入框手动切换模型」开关（同一交互入口的另一维度约束）

## 1. 现状与问题

### 1.1 输入框的模型候选没有任何用户维度约束

`/api/portal/models`（[app/api/portal/endpoints/models.py:66](app/api/portal/endpoints/models.py#L66)）只按 `is_active`（与可选 `type`）过滤，**不区分调用者**。EmbedChat 拉全量后自己筛 `llm | multimodal`：

```ts
// frontend/src/views/EmbedChat.vue :: fetchModels
const res = await modelApi.list();
availableModels.value = res.data.filter((m) => (m.type === "llm" || m.type === "multimodal") && m.is_active);
```

结果是：任何一个能打开对话页的用户，都能把输入框模型切到平台里任意一个已启用模型——包括最贵的那个。

### 1.2 后端对「手动覆盖」没有任何校验

`resolve_runtime_model` 的优先级是（[app/services/ai/config.py:108](app/services/ai/config.py#L108)）：

```
显式覆盖(debug_options.model) > 全局 debug 配置 > 智能体版本配置 > 系统默认
```

其中显式覆盖与全局 debug 都没有白名单校验，等于**前端是唯一防线**：改一下请求 body 就能用任意模型。所以"只在 UI 上隐藏"不成立，必须有一个后端校验点。

### 1.3 与已交付的版本级开关是正交两维

| 维度 | 作用对象 | 版本级 `allow_model_switch`（已交付） | 本设计：模型白名单 |
| --- | --- | --- | --- |
| 粒度 | — | 智能体版本：该智能体对**所有人**一刀切 | 角色 / 用户：**同一个人**在不同智能体上的差异 |
| 典型诉求 | — | 「这个智能体太敏感/太贵，谁都不许换」 | 「李四不该碰 GPT-4o，张三可以」 |
| 落点 | — | 输入框隐藏切换器 + 发送时不下发覆盖 | 输入框只列白名单 + 后端拒绝越权覆盖 |

两者组合后的输入框语义见 §4.8。

## 2. 目标

1. 支持**角色级**与**用户级**「聊天可用模型」白名单；用户级与角色级取**并集**。
2. **空白名单 = 不限制**（未配置的人行为与今天完全一致）。
3. **不影响智能体默认配置的模型**，也不影响系统默认模型与全局 debug 通道——只约束"用户手动切换"这一路。
4. **输入框候选 = 智能体默认模型 ∪ 白名单模型**（去重）。智能体指定用哪个模型就必须能在候选里看到它，否则会出现"正在用的模型不在列表里"的荒谬体验。
5. **智能体默认模型永远可以显式选中**：它同时是"允许的显式覆盖集合"的一员，用户选它不会被后端拒绝（见 §4.5）。这一条是第 4 条的必然推论，漏了就会造出"选了当前正在用的模型反而被拒"的 bug。
6. 越权覆盖被**明确拒绝**（不是静默回落），并留下可追溯的应用日志。
7. 生效范围仅**聊天输入框**（EmbedChat 的模型切换器）。
8. **零数据库迁移**。

## 3. 范围

### 3.1 纳入

- 权限聚合与读写新增 `model` 资源类型（角色级 + 用户级）。
- 新增 `GET /api/portal/models?scope=chat`（非管理员按白名单过滤）。
- `resolve_runtime_model` 的显式覆盖分支加白名单校验。
- 角色管理 / 用户管理的权限弹窗新增「可用模型」资源页。
- EmbedChat 使用 `scope=chat` 候选，并与版本级开关组合。
- 上述全部改动的自动化测试与验收步骤。

### 3.2 不纳入（含理由）

| 项 | 理由 |
| --- | --- |
| 审计表落库（可在审计页查看） | 应用日志已够定位；多一张写入链路与查询界面，收益不抵成本。若后续有合规要求再加 |
| 智能体调试页（AgentDebug）、任务提示词编辑器、Prompt Studio | 已确认只约束聊天输入框；调试页保留自由选模型是排障需要 |
| 系统默认模型、全局 debug 配置 | 这两条不是"用户手动切换"，一律不校验、不因白名单改变 |
| 智能体版本模型被"拦截" | 不存在：智能体版本指定的模型**始终可用**，并且被额外加入"允许显式覆盖"的集合（§4.5）。白名单只限制**别的**模型能不能被手动切到 |
| 嵌入模型（embedding）等其它类型 | 聊天输入框只列 `llm | multimodal`；按类型再分维度属于过度设计 |
| 「智能体 × 模型」二维矩阵 | 表达力过剩，配置与排查成本陡增 |
| 越权时自动降级到某个可用模型 | 见 §6.2：静默改行为比报错更难排查 |
| 白名单命中模型的成本/配额提示 | 属于另一个议题（配额中心），不在本次范围 |

## 4. 设计

### 4.1 数据模型：复用 `ai_agent_resource_permissions`，零迁移

该表已是多态资源权限表，且 `user_id` / `role_id` 二者其一即可（[app/models/permission.py:27](app/models/permission.py#L27)）：

| 字段 | 本次取值 | 说明 |
| --- | --- | --- |
| `resource_type` | `"model"` | 与既有 `agent` / `dataset` / `api` / `metadata` / `menu` / `element` / `forbidden_tool` / `forbidden_command` 并列 |
| `resource_id` | `AIModel.model_id` | 注意**不是** `ai_models.id`，与 `debug_options.model` 的比较口径一致 |
| `role_id` | 角色级白名单 | 角色权限弹窗写入 |
| `user_id` | 用户级白名单 | 用户权限弹窗写入 |
| `enabled` | `1` | 与其它资源类型一致，查询时过滤 `enabled == True` |

选择理由：现有 `get_user_permissions` 聚合（[app/services/permission_service.py:34](app/services/permission_service.py#L34)）本来就是 **user 直配 ∪ role 配置**——正好等于本设计要求的合并规则；缓存失效链路（`_invalidate_user_cache`，角色改动时遍历该角色全部用户）也已具备，无需重建。

### 4.2 语义规则（四条，务必与 `element:` 反着理解）

1. **空白名单 = 不限制**：该用户（角色并集后）没有任何 `model` 记录 → 允许全部模型。
   ⚠️ 这与 `element:` / `menu:` 的"列出才有权限"**相反**，必须在这三处写死注释：聚合处、判据函数处、前端资源页文案（"未配置 = 不限制"）。
2. **并集**：`允许集合 = ∪(用户所属角色的 model 记录) ∪ (用户直配的 model 记录)`。
3. **管理员直通**：`user.role == 'admin'`（与 `require_permission` 的 admin 直通一致）不受限，避免管理员把自己锁在门外。
4. **只约束显式覆盖**：白名单只在"请求里显式带了 model"时参与判断。
5. **智能体默认模型是天然豁免项**：`允许显式覆盖集合 = 白名单 ∪ {该智能体版本的编排模型}`。用户"再选回智能体默认模型"永远合法；白名单限制的是**其它**模型。少了这一条，用户在输入框里选自己当前正在用的模型也会被拒。

统一判据函数（唯一入口，供过滤接口与校验点共用）：

```python
# app/services/permission_service.py
async def get_chat_allowed_model_ids(self, user_id) -> Optional[set[str]]:
    """返回该用户聊天可手动切换的模型集合；None 表示不限制（未配置）。"""
```

约定：**返回 `None` = 不限制**；返回非空 `set` = 白名单（**不含**智能体默认模型——豁免项由调用方叠加，因为这个函数只回答"这个人被允许碰哪些模型"，不关心具体是哪个智能体）；并集后为空集时**也返回 `None`**（避免"配了空 = 全禁"这种破坏性歧义）。

两个调用方各自叠加豁免项：

| 调用方 | 实际使用的集合 |
| --- | --- |
| `scope=chat` 候选过滤（§4.4） | 因不知道具体智能体，按纯白名单过滤；前端再补上当前智能体默认模型（§4.8） |
| 显式覆盖校验（§4.5） | `白名单 ∪ {config.model_name}`（此处的 `config` 就是该次请求的智能体版本配置） |

### 4.3 后端改动清单（文件级）

| 文件 | 改动 |
| --- | --- |
| `app/schemas/permission.py` | `PermissionSet` 加 `models: List[str] = Field(default_factory=list)`；`PermissionSetDetail` 加 `models: List[ResourceDetail]`（弹窗要显示已选模型的名称）。`PermissionUpdate` 继承 `PermissionSet`，接口自动获得该字段 |
| `app/services/permission_service.py` | ① `_aggregate_permissions` 加 `resource_type == "model"` 分支；② `update_user_permissions` / `update_role_permissions` 的 `types_to_update` 加 `"model"` 并写入 `ResourcePermission(resource_type="model", resource_id=model_id)`（两处都要，否则保存时会把白名单删掉却不重建）；③ 新增 `get_chat_allowed_model_ids`；④ `_fetch_permission_details` 为 model 补展示名（查 `ai_models.name`，找不到时回退 `model_id`） |
| `app/services/permission_service.py`（缓存键） | `_get_cache_key` 的版本号 `v3` → `v4`：新增字段后旧缓存里没有 `models`，会解析成空列表（= 不限制），导致"刚配的白名单不生效"难以排查。升版本号强制全量重算 |
| `app/api/portal/endpoints/models.py` | `list_models` 增加 `scope: str = None`；`scope == "chat"` 且非管理员且判据函数返回非 `None` 时，追加 `AIModel.model_id.in_(allowed)` |
| `app/api/v1/endpoints/chat.py` | `create_chat_completion` 的 `debug_options` 清洗段加白名单校验（见 §4.5，紧邻既有 `resource_scope` / `injected_context` 清洗） |
| `app/services/ai/agent_manager.py` | 新增 `published_agent_model_name(session, agent_id, version_id)`：取已发布版本的编排模型名，**仅用于端点校验时的豁免判断**（前端不再需要它，故未扩展 `attach_published_model_switch_flags`，也没有新增响应字段） |
| `frontend/src/api/model.ts` | 新增 `listAvailableForChat()`（`GET /api/portal/models?scope=chat`）；**既有 `list()` 签名与语义保持不变**，管理端调用点不受影响 |
| `frontend/src/views/Roles.vue`、`frontend/src/views/Users.vue` | 权限弹窗新增「可用模型」资源页（见 §4.7） |
| `frontend/src/views/EmbedChat.vue` | `fetchModels` 改用 `listAvailableForChat()`；候选 = 白名单 ∪ 当前智能体默认模型（去重 + 「· 智能体默认」标记）；组合语义与残留覆盖清理（见 §4.8） |

### 4.4 过滤接口：`GET /api/portal/models?scope=chat`

- 不带 `scope`：行为与今天完全一致（全量），**版本配置的编排/合成模型候选、系统配置页、模型管理页全部不受影响**——这正是"不影响智能体默认配置"的实现方式。
- `scope=chat`：非管理员且白名单非空时只返回白名单内的模型；管理员或未配置者返回全量。
- 端点内直接调用 §4.2 的判据函数（`get_current_user` 已提供 `user_id` / `role`）。
- 该接口**不知道调用者正在用哪个智能体**（同一份响应可能被多个智能体上下文复用），所以它只做白名单过滤；"补上当前智能体默认模型"由前端在选定智能体后完成（§4.8）。

### 4.5 校验点：聊天端点层的 debug_options 清洗段（不是 `config.py`）

**落点修正说明**：原设计想把校验放在 `resolve_runtime_model_info`（[config.py:94](app/services/ai/config.py#L94)），调研后发现三个问题：该函数签名里没有用户上下文（只有 `config` / `debug_options` / `model_override` / `phase`），而它的调用方（`agent_service._resolve_runtime_model_info_safe` → `route_step` / `resume`）也拿不到干净的请求用户；把 `user_id` 一路透传要改 4 个调用点的签名，且异常要从 pipeline 深处冒泡才能变成 HTTP 响应。

真正的入口是 `create_chat_completion`（[app/api/v1/endpoints/chat.py:1691](app/api/v1/endpoints/chat.py#L1691) 附近），那里**已经有"服务端清洗客户端 `debug_options`"的既有模式**（`resource_scope` 被 `pop`、`injected_context` 被 `sanitize_injected_context`），而且同一作用域内 `user_info`、`db`、`completion_request.agent_id / version_id / conversation_id` 全部可得。所以校验放在这里，与既有安全清洗写在同一个段落：

```python
# app/api/v1/endpoints/chat.py :: create_chat_completion（紧跟 resource_scope 清洗之后）
# 模型白名单只约束「客户端显式注入的模型覆盖」；未配置白名单 = 不限制。
override_model = str(effective_debug_options.get("model") or "").strip()
if override_model and str(user_info.get("role") or "") != "admin":
    allowed_model_ids = await PermissionService(db).get_chat_allowed_model_ids(chat_user_id)
    if allowed_model_ids is not None:
        # 智能体版本指定的模型天然豁免：用户「选回默认模型」必须始终合法
        agent_default_model = await published_agent_model_name(
            db, completion_request.agent_id, completion_request.version_id
        )
        if agent_default_model:
            allowed_model_ids = allowed_model_ids | {agent_default_model}
        if override_model not in allowed_model_ids:
            logger.warning(
                "chat model override rejected: user=%s model=%s agent=%s conversation=%s",
                chat_user_id, override_model,
                completion_request.agent_id, completion_request.conversation_id,
            )
            raise HTTPException(
                status_code=403,
                detail="该模型不在你的可用范围内，请联系管理员调整",
            )
```

配套一个可测试的查询助手（放在 [app/services/ai/agent_manager.py](app/services/ai/agent_manager.py) 的 `AgentManager` 内，与既有的 `get_version_config` / `_latest_published_versions_by_agent` 同处）：

```python
@staticmethod
async def published_agent_model_name(
    session: AsyncSession, agent_id: Optional[str], version_id: Optional[str] = None
) -> str:
    """返回该智能体「已发布版本」配置的编排模型名；查不到返回空串。

    仅供模型白名单的豁免判断使用：白名单限制手动切换，但不能连智能体自己
    指定的模型都拦掉。
    """
```

要点：

- 只校验请求体带来的 `effective_debug_options["model"]`，**不校验** `get_debug_option("model")`（全局 debug 配置）、系统默认；智能体版本模型不但不拦截，还作为豁免项加入放行集合。
- `agent_id` 为空（多智能体路由场景）时拿不到豁免项：此时前端也不会展示"某智能体的默认模型"，用户提交的覆盖一律按白名单判断，行为正确。
- 该校验位于端点层，因此**只在真实聊天请求上生效**；后台任务、定时任务、恢复会话（`resume.py` 用服务端保存的 `debug_options`）都不经过这里，天然不误伤。
- **管理员判据**沿用既有约定 `user.get("role") == "admin"`（与 `require_permission` 的直通规则一致，[app/core/dependencies.py:150](app/core/dependencies.py#L150)）；不要把"拥有全部 element 权限的业务角色"当作管理员，否则会与既有语义分叉。
- 白名单**不负责**模型是否启用/是否存在：那是既有模型注册表逻辑（`_lookup_registered_model`）的职责，两者不重复判断。
- 拒绝用 `HTTPException(403)`，与同一函数里已有的"该会话不属于当前用户"保持同一种表达，前端能直接展示 `detail`。

### 4.6 缓存与生效时机

- 读取走 `get_user_permissions` 既有缓存（Redis `sys:auth:permissions:v4:user:{id}`）。
- 写入后：用户级 → `_invalidate_user_cache(user_id)`；角色级 → 既有逻辑已遍历该角色下全部用户清缓存。无需新增失效代码。
- 缓存键升到 `v4` 后首次访问自然回源，无需手工清 Redis。

### 4.7 前端：权限弹窗新增「可用模型」资源页

- 位置：`Roles.vue` 与 `Users.vue` 的权限弹窗，与「智能体 / 数据集 / 知识库 / 菜单 / 功能点」并列（复用同一套 `permissionData` + `activeResTab` 多选交互与读写接口，`permissionData.models` 为新数组）。
- 形态：可搜索的多选列表（模型可能几十条）+ 已选计数 + 全选/清空；搜索框复用列表过滤，不引入新组件（与平台其它资源页保持一致的视觉）。
- 文案：资源页顶部固定一行说明——「未配置 = 不限制；配置后该角色/用户只能使用勾选的模型（与其角色白名单取并集）」。
- 只列 `llm | multimodal` 且 `is_active` 的模型；已选但已停用/已删除的模型：**保留勾选态并在名称后标注「已停用」，不自动清除**（否则一次保存就会静默丢失配置，与既有"未知值保留"的处理思路一致）。

### 4.7.1 资源页的模型搜索（实现后增补）

模型动辄几十条，§4.7 的「可搜索」落成如下三条语义（已与用户确认）：

1. **只给「可用模型」页加搜索框与分组**：其它资源页（智能体/数据集/知识库/API/菜单/功能点）保持原样，改动面最小。
2. **已勾选项单独成段、始终显示**（默认视图「已选 N 个」在上、「其余 M 个」在下），即使不匹配搜索词也不被过滤。理由是权限配置场景下"不能让我看不见我选了什么"——否则用户会以为白名单丢了，进而重复勾选或误以为保存失败。
3. **「全选本页」只作用于当前可见列表**（= 已选段 ∪ 其余段的搜索结果），不会选中看不见的项。

实现要点：

- **分组优先于过滤**：模型动辄几十条，已勾选项混在原序里会被淹没（用户实测反馈「候选的太多了，已选择了的模型被淹没了」）。因此默认视图就分两段渲染——「已选 N 个」在上、「其余 M 个」在下，各带一个小标题；这比"搜索时才置顶"更直接，用户不需要先输入关键词。
- 纯函数 `groupPermissionModels(models, query, selectedIds) => { selected, others }`：`selected` = 全部已勾选（按列表**原序**，不是勾选顺序，且搜索时**不过滤**）；`others` = 未勾选且匹配搜索词的（搜索词为空则为全部未勾选项）。匹配字段为 `name` / `display_name` / `platform_name` / `model_id` / `id`，大小写不敏感，不改动入参。搜索框显示阈值复用 `shouldShowModelSearch(count)`（≥6）。
- **单一接入点**：`currentResources` 的 `models` 分支把两段拍平（`[...selected, ...others]`）。列表渲染、底部「已勾选 N」、「全选本页」的 `isAllSelected` / `toggleSelectAll` 都基于 `currentResources` / `selectableResources`，拍平后这些行为完全不变；只有渲染层额外读一份 `modelResourceGroups` 来插入两段标题。
- `toggleSelectAll` 是「用可见项替换整个数组」的语义；因为已勾选项始终留在可见项里（无论搜索与否），搜索态下点「全选本页」不会丢掉、也不会多出看不见的已选配置。
- 搜索无结果时空态文案为「（没有匹配的模型）」，与「（暂无资源）」区分（后者说明该页确实没有可选资源）。
- 切换资源 Tab 时清空搜索词，避免切到别的页再回来看到一份"被过滤过"的列表却找不到原因。
- 与「已停用」标注共存：已勾选的停用模型因第 2 条始终可见，标注照旧。

### 4.8 前端：EmbedChat 的组合语义

模型候选改为 `listAvailableForChat()` 之后，输入框按下表决策（在既有 `manualModelSwitchAllowed` 计算属性附近统一实现）：

| 版本 `allow_model_switch` | 白名单 | 输入框候选 | 表现 |
| --- | --- | --- | --- |
| 禁止 | 任意 | — | **隐藏**切换器（既有逻辑） |
| 允许 | 未配置 | 全量 | 现状不变（候选远多于阈值，必然显示） |
| 允许 | 已配置 | **仅白名单候选**（去重，不并入智能体默认模型） | 候选 **≥1 个就显示**：下拉里「使用默认模型」+ 至少一个模型 = 至少两项可选 |
| 允许 | 已配置 | 候选为空（勾选的模型全被停用） | **隐藏 + 只读提示**（不给空下拉） |

候选构造规则（在既有 `manualModelSwitchAllowed` 计算属性附近统一实现，并与它共用一个纯函数，便于单测）：

1. 取 `scope=chat` 的候选（已按白名单过滤），按 `model_id` 去重——**候选只来自白名单**；
2. 只要候选 ≥1 就显示切换器。下拉的第一项是 `ChatInput` 固有的「使用默认模型」（= 不下发覆盖、跟随智能体/平台默认），它已经把「选回默认模型」这条路覆盖掉了，所以**不再把智能体默认模型单列成一个可选项**：选它与选「使用默认模型」效果完全一样，重复且占位（`agentDefaultModel` / `hasAgent` 两个入参据此移除）；
3. 若当前生效的 `overrideModel` 未出现在候选里 → 清掉本机覆盖、回落到智能体默认模型（同时刷新上下文用量统计）；
4. **候选为空时的兜底**（白名单里勾选的模型后来全被停用）：不静默消失，改为在切换器位置显示只读提示「你的可用模型已全部停用，请联系管理员」。否则管理员无法区分"白名单生效了"与"功能坏了"。

- 语义边界：白名单**放宽不了**智能体的默认模型，也**收紧不了**它——用户不手动切换时，用的永远是智能体版本指定的模型。

## 5. 兼容性与回归保证

1. **存量用户零变化**：没有任何 `model` 记录 → 判据返回 `None` → 过滤接口不加条件、校验点直接放行。这是本次设计最关键的一条。
2. **管理端接口零变化**：`list()` 不带 `scope`，版本配置候选、系统配置页、模型管理页继续拿全量。
3. **非"手动切换"的模型解析链路零变化**：合成模型、系统默认、全局 debug 通道均不校验；智能体版本模型本身不被拦截，并且作为豁免项加入"允许显式覆盖"的集合（§4.5）。
4. **权限读写向后兼容**：新增字段有默认值。为避免"角色原本配了白名单、被一个不带 `models` 的旧客户端保存权限后静默清空"，实现时用 `model_fields_set` 区分两种情形：请求**未提交** `models` 字段 → 保留数据库原值；请求提交了 `models: []` → 视为显式清空（回到"不限制"）。这与仓库既有的"新字段只有显式出现才落库"约定一致（见版本配置的 `allow_model_switch` 更新守卫）。
5. **缓存升级不改变结果**：`v3 → v4` 只是强制回源，回源结果与今天一致（无记录 = 不限制）。

## 6. 已知限制与副作用

1. **只约束聊天输入框**：AgentDebug / 任务提示词编辑器 / Prompt Studio 仍可自由选模型。这是明确取舍（排障需要），意味着白名单不是"平台级模型管控"，而是"聊天场景的模型管控"。
2. **越权即报错**：正常路径下前端已过滤，能触发说明是绕过或白名单刚变更。选择拒绝而非静默回落，是为了让"模型没生效"这类问题一次就能定位（日志里能直接看到被拒的模型名）。
3. **管理员不受限**：拥有 admin 身份的人可以选任意模型。若将来需要"管理员也受限"，需要另立规则，不应在本次偷偷加。
4. **旧前端保存权限不会清空白名单**：按 §5.4 用 `model_fields_set` 区分"未提交"与"显式清空"，因此不同版发布也不会误删配置。
5. **生效有两个时间点**：权限缓存（秒级，写入即失效）与用户已打开的旧页面（需刷新才拿到新候选）。后端校验始终以最新白名单为准，因此不会出现"越权成功"。
6. **白名单与智能体默认模型的关系是"叠加"而非"冲突"**：候选 = 白名单 ∪ 智能体默认模型，所以智能体指定用 A、白名单只有 B 时，切换器里能看到 A（带「· 智能体默认」标记）和 B，用户选 A 也不会被后端拒绝（§4.5 的豁免项）。只有当用户手动切换到**既不在白名单、又不是当前智能体默认模型**的模型时才会被拒。切换器 tooltip 固定补一句「当前使用智能体指定的模型，可切换到：…」，让用户理解默认项从哪来。
7. **同一份 `scope=chat` 响应可能服务多个智能体**：接口不知道智能体上下文，默认模型由前端在选定智能体后并入，因此"切智能体"是候选变化的一个触发点，实现时要把它纳入候选计算的依赖（否则会出现切换智能体后候选没刷新）。

## 7. 测试计划

### 7.1 后端

- **判据函数**：无记录 → `None`；角色有 2 个 → 返回该 2 个；用户 + 角色 → 并集；并集为空 → `None`；admin → `None`。
- **聚合**：`_aggregate_permissions` 能把 `resource_type="model"` 收进 `models`；`_fetch_permission_details` 能补出模型展示名，找不到定义时回退 `model_id`。
- **读写**：`update_role_permissions` / `update_user_permissions` 保存后白名单未被误删（回归 §4.3 的两个 `types_to_update`）；提交空列表 → 变为不限制。
- **过滤接口**：`scope=chat` 无白名单 → 全量；有白名单 → 只含白名单；管理员 → 全量；不带 `scope` → 全量（关键回归）。
- **校验点**：白名单内含该模型 → 放行；不含且不等于智能体默认模型 → 拒绝且日志含模型名；未配置 → 放行；**智能体默认模型不在白名单但被显式选中 → 放行**（本次最关键的一条断言）；全局 debug 通道不在白名单 → 放行；`user_id` 缺失（后台任务）→ 放行。
- **缓存**：旧键不存在时回源；写入后用户缓存被清；改角色后该角色用户缓存被清。

### 7.2 前端（`pytest --confcutdir=tests/frontend`）

- 契约：`Roles.vue` / `Users.vue` 含「可用模型」资源页与"未配置 = 不限制"文案；`modelApi` 有 `listAvailableForChat`；EmbedChat 使用并集候选、含「· 智能体默认」标记与残留覆盖清理。
- 纯函数（node harness）：候选决策函数按「版本开关 × 白名单 × 智能体默认模型」三类输入产出 `{ visible, options }`，至少覆盖：版本禁止 → 不显示；未配置白名单 → 全量；白名单 2 个且默认模型不在白名单 → 3 个候选（并集去重）；白名单 1 个且默认模型在白名单内 → 去重后 1 个 → 不显示；白名单 1 个且默认模型不同 → 2 个候选 → 显示；白名单全为停用模型且智能体无默认模型 → 并集为空 → 输出提示文案态（不静默消失）。

### 7.3 手工验收

1. 管理员在角色管理里给 `default` 角色勾 2 个模型 → 用该角色账号刷新对话页 → 输入框只列这 2 个 **+ 当前智能体的默认模型（带标记）**。
2. 该账号在输入框里选"智能体默认模型"发一条消息 → **应当正常回复**（豁免项生效，这是最容易漏的一条）。
3. 该账号在浏览器控制台伪造 `debug_options.model` 为白名单外模型发一条消息 → 应被拒绝并提示。
4. 给该账号单独加第 3 个模型（用户级）→ 刷新后能选到（验证并集）。
5. 清空该角色白名单 → 恢复全量（验证"空 = 不限制"）。
6. 打开版本配置抽屉确认编排/合成模型候选**仍是全量**（验证不影响智能体默认配置）。
7. 在同一会话里切换智能体（@ 另一个智能体）→ 候选里的"默认模型"标记随之切换（验证 §6.7 的依赖处理）。

## 8. 验收标准

- [ ] 未配置白名单的用户，输入框候选、可切模型、后端行为与改动前完全一致。
- [ ] 角色级白名单生效：输入框列白名单；越权请求被拒绝并留日志。
- [ ] 用户级白名单与角色级取并集。
- [ ] **输入框候选 = 白名单 ∪ 智能体默认模型**（去重），默认模型带标记；用户选它不会被后端拒绝。
- [ ] 白名单为空 = 不限制，且"配了又清空"能真正回到不限制。
- [ ] 智能体版本模型始终可用；合成模型、系统默认、全局 debug 三条链路不因白名单而改变。
- [ ] 版本配置抽屉、系统配置页、模型管理页的候选仍为全量。
- [ ] 版本级开关 × 白名单的组合语义全部符合 §4.8（含"并集去重后 ≤1 才隐藏"与"并集为空时给提示而非静默消失"）。
- [ ] 无新增数据库迁移；`tests/frontend` 全量与新增后端测试通过；`vue-tsc` 零新增类型错误。

## 9. 未纳入（后续可选议题）

- 白名单越权的审计表落库与查询界面。
- 「智能体 × 模型」维度的细粒度矩阵，以及"按智能体再收窄白名单"。
- 与配额/成本中心联动（例如白名单之外再限制单用户在高价模型上的调用次数）。
- 白名单变更后的站内通知（"你的可用模型范围已调整"）。
- 把白名单能力扩展到调试页与任务提示词编辑器（需先解决"排障用不了模型"的矛盾）。
