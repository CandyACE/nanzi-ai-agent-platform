# 模型管理思考模式配置设计

日期：2026-08-07

状态：已实现（AgentScope 原生参数方案）

## 1. 目标与范围

在系统设置的“模型管理 → 高级设置”中增加思考模式相关配置，使管理员可以为每个已登记模型保存思考能力和思考强度选项。

完成数据库存储、后端接口契约、前端表单展示、创建/编辑回显和保存，并将注册模型配置接入统一 AgentScope 模型创建链路。EmbedChat、AgentDebug 输入框级别的临时控制仍不在本阶段范围内。

## 2. 配置字段

`ai_models` 增加以下字段：

| 字段 | 类型 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `thinking_enable` | Boolean | `false` | AgentScope `Parameters.thinking_enable` |
| `thinking_only` | Boolean | `false` | 模型是否默认以思考模式运行 |
| `allow_disable_thinking` | Boolean | `true` | 是否允许用户关闭思考 |
| `reasoning_effort` | String，可空 | `NULL` | AgentScope `Parameters.reasoning_effort`；`NULL` 表示自动 |
| `supported_reasoning_efforts` | Text，JSON 数组 | AgentScope 六档 | 模型支持的思考强度集合 |

内部值与界面文案映射如下：

| 内部值 | 界面文案 |
| --- | --- |
| `NULL` | 自动（使用请求层默认值） |
| `none` | 无 |
| `minimal` | 极简 |
| `low` | 低 |
| `medium` | 中 |
| `high` | 高 |
| `xhigh` | 极高 |

`thinking_only` 参与后端未收到会话覆盖时的默认思考状态计算；`allow_disable_thinking` 控制前端显式关闭思考是否生效。两个字段都应完整持久化。

## 3. 后端契约

- SQLAlchemy `AIModel` 增加上述字段，并为旧记录提供与迁移默认值一致的 ORM 默认值。
- `AIModelCreate`、`AIModelUpdate`、`AIModelResponse` 和前端 `AIModel` 类型同步增加字段。
- `reasoning_effort` 只接受 AgentScope 的 `none`、`minimal`、`low`、`medium`、`high`、`xhigh`，也可以为 `NULL` 表示自动。
- `supported_reasoning_efforts` 只接受上述六档，去重并保持固定展示顺序；空列表拒绝保存。
- 非空 `reasoning_effort` 必须存在于 `supported_reasoning_efforts` 中。
- 非 LLM / 多模态模型也可以保存配置，但前端只在模型管理高级区域展示，不改变现有模型类型筛选行为。
- 模型连接测试接口不消费这些字段，也不因其存在改变当前测试请求。
- 旧模型记录通过 V117/V16 迁移重命名为 `thinking_enable`、`reasoning_effort`；`auto` 转为 `NULL`，历史 `max` 转为 AgentScope 的 `xhigh`。

为兼容 MySQL 与 PostgreSQL，支持强类型枚举的单字段使用字符串列；支持强度集合使用 Text 存储 JSON 数组，避免两套数据库方言对 JSON 默认值的差异。

## 4. 前端交互

高级设置现有“输入上下文”和“输出上限”之后增加思考配置区域。

1. “思考模式”是胶囊/开关式控件，默认关闭。
2. 只有 `thinking_enable=true` 时，才显示“默认思考模式”“允许关闭思考”“默认思考强度”“支持的思考强度”。
3. 关闭“思考模式”只隐藏相关控件，不清空已配置值；再次打开时恢复原配置。
4. 新建模型按设计默认值初始化；编辑和克隆模型使用接口返回值回显。
5. “默认思考强度”使用单选下拉，自动对应 `NULL`；“支持的思考强度”使用 AgentScope 六档复选项，每档独立卡片展示，至少保留一个选项。
6. 当默认强度对应的支持项被取消勾选时，前端应自动切换到当前列表中的第一个强度；若默认值为“自动”，则不受支持项勾选影响；保存前仍由后端再次校验。
7. “默认思考模式”只决定没有会话覆盖时的初始状态；前端显式开启/关闭思考不受该字段影响，显式关闭是否生效只由“允许关闭思考”决定。

高级设置的“已配置”提示应在任一上下文、输出或思考配置存在时显示，避免用户关闭思考模式后误以为思考配置丢失。向量模型隐藏高级设置。

## 5. 数据迁移

按仓库迁移约定分别新增：

- MySQL：V117 迁移文件，重命名思考字段并转换 `auto` / `max` 历史值；
- PostgreSQL：V16 迁移文件，使用 PostgreSQL 幂等写法完成同样字段重命名和数据转换。

迁移不得修改已有迁移文件，不直接操作本地或线上数据库。两套迁移的字段名、默认值和描述必须一致。

## 6. 测试验收

- 后端创建模型：不传新增字段时返回设计默认值。
- 后端创建模型：传入完整思考配置后，查询接口返回相同配置。
- 后端更新模型：可以分别更新开关、思考强度和支持列表；旧值不被无关字段更新覆盖。
- 后端校验：非法强度、空支持列表、默认强度不在支持列表中时返回 422。
- 前端契约：高级设置仅在思考模式打开时渲染相关参数；关闭后值仍保留；新建/编辑/克隆均包含字段。
- 迁移检查：MySQL 与 PostgreSQL 文件均只新增迁移，且通过 `git diff --check`。

## 7. 明确不做

- 不修改 EmbedChat、AgentDebug 输入框级别的请求参数控制。
- 不根据供应商自动识别或覆盖思考能力。
- 不增加 `chat_template_kwargs` 或供应商私有参数映射；运行时直接复用 AgentScope `OpenAIChatModel.Parameters`。
- 不改变现有上下文长度、输出 token 上限和模型连接测试行为。
