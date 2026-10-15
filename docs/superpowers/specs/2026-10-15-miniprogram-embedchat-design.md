# 小程序微端（微信自动开户 + 嵌入 EmbedChat）设计

- 日期：2026-10-15
- 涉及范围：平台新增 1 个受保护接口 + 1 张绑定表 + 1 个固定角色 + 1 个开关（**不新增权限码**，复用现有「代他人签发嵌入凭证」），EmbedChat 少量宿主适配；小程序工程（**仓库外**）新增 1 个云函数 + 2 个页面
- 小程序工程：`/Users/chenxiaolong/WeChatProjects/miniprogram-nanzi-ai`（微信云开发 quickstart 模板，AppID `wx1ca87185956d0071`）
- 迁移：`db-prod/V170`+`V171`、`db-prod-pg/V71`+`V72`（建表 + 角色/开关种子）
- 复用而非改造：`EmbedService.create_ticket()` / `exchange_ticket()` 与 EmbedChat 的 `?ticket=` 认证链路**零改动**

## 1. 背景与目标

把平台能力以「微信小程序微端」的形式对外提供：用户在小程序内静默登录，平台自动为其开设账号，并直接把 EmbedChat 页面嵌进小程序的 `web-view`。

**目标**：用户打开小程序 → 无需注册、无需密码、无需登录表单 → 直接在 EmbedChat 里对话。

**达成方式**：小程序云函数用 `cloud.getWXContext()` 取得**不可伪造**的 openid，带平台 API Key 调用平台接口；平台按 openid 自动开户并签发一张一次性 ticket；小程序把它交给 `web-view`。

## 2. 已核实的事实

### 2.1 平台侧（均已在代码中确认）

| # | 事实 | 出处 |
|---|---|---|
| 1 | `/embed/chat?ticket=` 由页面自行兑换，同一 ticket 并发去重、成功后清理 URL、失败区分 `origin_not_allowed` / `invalid_ticket` | `frontend/src/views/EmbedChat.vue:7324` |
| 2 | ticket 一次性、`GETDEL` 原子核销，TTL 默认 300s、上限 1800s | `app/services/embed_service.py:14,187` |
| 3 | 兑换后签发 `emb_ses_*`（24h 滑动续期），写 `auth:api_key:*` 缓存，并下发 `embed_session` Cookie | `app/services/embed_service.py:196-218` |
| 4 | `create_ticket` 支持 `target_user_id` 精确指定；目标用户必须 `status == 1` | `app/services/embed_service.py:48,70` |
| 5 | `allowed_origins` 为空时不校验 Origin，可原样留空 | `app/services/embed_service.py:172` |
| 6 | 需要 API Key 的 v1 接口挂 `v1_secured`；匿名公开接口挂各自模块的 `public_router` | `app/api/v1/api.py:5,22`、`app/api/v1/endpoints/embed.py:102` |
| 7 | **`is_v1_api_whitelisted` 对路径含 `/embed` 的请求直接放行细粒度权限检查**，且该白名单是**子串匹配**；它只跳过权限、不跳过 API Key | `app/core/v1_api_access.py:118-129`、`app/core/dependencies.py:185-187` |
| 8 | 自助注册 `/api/portal/auth/register` 建的是 `status=2` 待审核号，注册开关默认关闭，并会给管理员发通知 | `app/api/portal/endpoints/auth.py:211,330` |
| 9 | 无密码账号无法密码登录（`not user.password_hash` → `error_no_password`） | `app/services/auth_service.py:1049` |
| 10 | `generate_api_key()` 无条件签发长期 API Key，明文只在返回值中出现 | `app/services/auth_service.py:66` |
| 11 | 后台 `UpdateUserRequest` **不含 `user_name`**，账号名建后不可改 | `app/api/portal/endpoints/management.py:301` |
| 12 | 系统角色 `user.role` 只有 `admin`/`user`；业务角色（`Role`，唯一键 `code`）才是权限/配额/可见智能体的载体 | `app/api/portal/endpoints/management.py:52`、`app/models/permission.py:9` |
| 13 | **智能体可见性是白名单**：系统智能体必须在角色权限聚合出的 `allowed_ids` 内才可见，主入口智能体也不豁免（`main_first` 仅排序） | `app/services/ai/agent_manager.py:759-764` |
| 14 | 配额支持角色级策略 | `app/api/portal/endpoints/quota.py:113` |
| 15 | `SystemConfig.is_secret` **只做显示掩码、不加密存储**，且 `system_config_history` 另存明文副本 | `app/services/config_service.py:337-380`（无 encrypt 调用） |
| 16 | 迁移执行器无 `schema_migrations` 记录表，幂等必须写在 SQL 自身 | `db-prod/apply_sql.py` |
| 17 | 权限页「外部 API」的可分配项来自静态清单 `ASSIGNABLE_V1_API_RESOURCES`（当前 4 项），是该页唯一数据源 | `app/core/v1_api_access.py:9-44` |
| 19 | `create_ticket` 代客签票护栏：非 admin 且 `target_user_id` 不等于自己时，**必须**具备 `POST:/api/v1/embed/tickets` 权限，否则抛 `PermissionError` | `app/services/embed_service.py:79-94` |
| 18 | 平台**没有全局限流中间件**（`app/main.py` 仅挂 GZip / AccessLog / CORS / SecurityHeaders）；注册限流（IP 5 次/小时、账号名 3 次/小时）是 `register` 端点内的显式调用，不覆盖其它接口 | `app/main.py:398-410`、`app/services/auth_service.py:359-360,572` |
| 20 | ⚠️ **`ai_agent_users.id` 的 ORM 声明与真实 DDL 不一致**：ORM 写 `Column(Integer)`，DDL 却是 `BIGINT`。因此**凡新建关联该表的外键列，SQL 必须写 `BIGINT`**（MySQL 要求外键两侧整数类型完全一致，写成 `INT` 会报 errno 3780、导入直接失败），ORM 侧则跟平台既有做法用 `BigInteger` | `app/models/user.py:18` vs `db-prod/V0-init_yunshu_ai_agent_metadata.sql:11`；既有 6 处指向该表的 FK 全为 `BigInteger`（`app/models/permission.py:23`、`saved_report.py:26,57`、`artifact.py:19`…） |
| 21 | ⚠️ **`npx vue-tsc --noEmit` 在本仓库是空操作**：`frontend/tsconfig.json` 是 solution 型（`"files": []` + `references`），不带 `-b` 时**一个文件都不检查**、静默 `exit 0`——拿它做前端验收等于**永远通过**。真实检查必须用 `NODE_OPTIONS=--max-old-space-size=6144 npx vue-tsc -b --force`（等价写法 `-p tsconfig.app.json`，两者实测同为 79 条）；基线是全仓既有 **79 条** error TS，验收标准是「**不新增**」而非「0 错误」。⚠️ 本条**不是新发现**：`tests/CHECKLIST.md` 里 2026-10-12 的条目已记录过同一个坑（当时基线 67 条），但 `AGENTS.md` 里写的仍是那个不生效的命令，导致后续每人都会再踩一次 | `frontend/tsconfig.json:1-6`；探针实验（在 `src/` 放一个类型错误）证明 `--noEmit` exit 0 无输出、`-b` 能稳定报出该错误 |
| 22 | **`SystemConfig.vue` 的布尔配置必须显式注册进「开关白名单」**：该页**没有**「按类型自动识别布尔」的机制（`ConfigItem` 只有 `key/value/description/is_secret`），渲染是 `v-if/v-else-if` 链按 key 硬编码特判。开关共 **4 个分支**：`:5212` / `:5271` / `:5370` 三个白名单数组 + `:5158` 的专门分支（`hide_login_apikey`）。全平台共 **13 个**布尔配置，其中 12 个早已注册；`miniprogram_enabled` 首次**漏注册**，退化成手填 `true`/`false` 的文本框。已加契约测试 `tests/frontend/test_boolean_config_toggle_contract.py` 从迁移 SQL 反查布尔 key 并断言全部有开关分支 | `frontend/src/views/SystemConfig.vue:5158,5212,5271,5370`；迁移侧 13 个布尔 key 见 `db-prod/V*.sql` |

事实 7 是本设计的一处**必须绕开的陷阱**：新接口路径落在 `/api/v1/embed/...`，会被白名单跳过权限检查，因此**接口内部必须显式校验权限**，否则任何平台用户的 API Key 都能伪造 openid 为他人开户。

### 2.2 微信侧（官方文档确认）

| # | 事实 | 影响 |
|---|---|---|
| 1 | 「个人类型的小程序暂不支持使用」`web-view` | **必须企业/组织主体** |
| 2 | 业务域名仅支持 https、不支持 IP、**必须已 ICP 备案**，新备案域名需 **24 小时**后方可配置 | 排期硬等待 |
| 3 | 每个小程序最多配 300 个域名；配好后任意合法子域名通用 | 门槛比预期低 |
| 4 | 「每个页面只能有一个 web-view，会自动铺满整个页面，并覆盖其他组件」 | 聊天页必须是独立整页 |
| 5 | `bind:message` 仅在**小程序后退、组件销毁、分享、复制链接**时触发，`e.detail.data` 是多次 `postMessage` 攒成的数组；「不支持除 JSSDK 提供的接口之外的通信」 | **不存在实时 H5→小程序通道** |
| 6 | `wx.miniProgram.navigateTo` / `navigateBack` / `redirectTo` / `reLaunch` / `switchTab` 可用 | 唯一**即时**通道 |
| 7 | 支持的 JSSDK 无 `chooseMessageFile`；有 `chooseImage`/`previewImage`/`scanQRCode`/`getLocation` 等 | 页内无法「从聊天记录选文件」 |
| 8 | 可用 `window.__wxjs_environment === 'miniprogram'`、`wx.miniProgram.getEnv`、UA 中的 `miniProgram` 检测环境；8.0.16/8.0.17 起 UA 携带小程序 appid | 环境检测与来源校验可行 |
| 9 | 官方 tip：iOS 下 JSSDK 无响应可在 src 后加 `#wechat_redirect`；避免链接含中文 | 白屏规避 |
| 10 | 云函数内 `cloud.getWXContext()` 返回微信注入的 `OPENID`/`UNIONID`/`APPID`，**调用方无法伪造** | openid 的可信来源 |
| 11 | `wx.downloadFile` 要求域名在**「downloadFile 合法域名」**白名单内；该白名单与**业务域名**是两套独立配置 | 原生文件页要下载平台文件，两个域名都必须配 |

来源：[web-view 组件](https://developers.weixin.qq.com/miniprogram/dev/component/web-view.html)、[业务域名](https://developers.weixin.qq.com/miniprogram/dev/framework/ability/domain.html)。

### 2.3 小程序工程现状

| # | 事实 |
|---|---|
| 1 | 工程为**微信云开发 quickstart 模板**，`projectname` 仍是 `quickstart-wx-cloud`，业务代码尚未编写 |
| 2 | `miniprogram/app.json` 只有模板页面 `pages/index/index`、`pages/example/index` |
| 3 | `cloudfunctions/` 下只有模板云函数 `quickstartFunctions`，其 `index.js` 内**已有现成的 `getOpenId`**（`cloud.getWXContext()`），可直接借鉴 |
| 4 | `miniprogram/envList.js` 的 `envList` 为**空数组**——云开发环境尚未创建 |
| 5 | `urlCheck: true`（开发者工具会校验域名合法性） |

## 3. 决策记录

| # | 决策 | 结论 |
|---|---|---|
| D1 | 账号口径 | **外部公众用户静默开户**：openid 即身份，免审核、免密码 |
| D2 | 权限边界 | 新建固定业务角色「小程序用户」，可见智能体与配额由管理员在后台配 |
| D3 | 角色种子 | **只种空角色**，不种任何权限行（权限由管理员后台分配） |
| D4 | 风控 | **不做防刷限流**（维度全部失效，见 §7.3），改为**角色配额兜底 + 高阈值熔断 + 开户可审计** |
| D5 | 小程序形态 | 原生首页 + 聊天 `web-view` 页 + 原生文件页 |
| D6 | 判定依据 | **按 openid（显式绑定表）**，不按 `user_name` |
| D7 | openid 来源 | **云函数 `cloud.getWXContext()`**，不在平台侧做 code2session |
| D8 | 平台接口暴露面 | **不对外公开**：接口需 API Key，且**内部显式校验权限**（绕开事实 7 的白名单） |
| D9 | AppSecret | **平台不需要**（openid 由微信注入云函数） |
| D10 | 信任模型 | 平台信任持有专用 API Key 的云函数传来的 openid，与既有「宿主后端代客签票」同一模型 |
| D11 | 小程序工程落位 | **仓库外**：`/Users/chenxiaolong/WeChatProjects/miniprogram-nanzi-ai`，本仓库只做平台侧与 H5 |
| D12 | 签票方式 | 小程序先换 ticket，web-view URL 由小程序构造；H5 认证链路不改 |
| D13 | 微信身份存放位置 | **独立绑定表**，不在 `ai_agent_users` 加列。依据：openid = 用户 × 单个 AppID，unionid = 用户 × 开放平台账号（微信官方 UnionID 机制），未来做网站应用扫码登录会拿到**另一个 openid**，一列装不下。平台既有风格同样按基数选：一对一的 `dept_code`/`org_path` 在用户表，多对多的用户↔角色用独立表 |
| D14 | 微端账号的 web 登录 | **暂缓**（用户 2026-10-15 决定：改用户名先不做，后面再说）。注意当前**零开发**即可部分达成——管理端已有 `POST /users/{user_id}/set-password`（无需旧密码），管理员给微端账号设个密码后，用户即可用其 `user_name`（`wx_<hash>`）+ 密码登录 web，只是名字不好记。详见 §6.4 |
| D15 | 设置登录名的前置条件 | 只允许「**从未产生业务引用**」的账号设置/修改登录名——`user_name` 被 `agent` / `knowledge` / `slash_command` 的 `created_by` 当作引用键，改名会使引用悬空。微端账号因空角色（D3）而天然满足该条件，但仍须显式校验 |
| D16 | 管理端展示 | 用户管理页新增「微信绑定」tab（**一行 = 一条绑定**）+ 用户列表加 `wechat_bound` 标识；openid/unionid **默认脱敏**，明文走独立接口按需取（权限升到 `element:user:edit` 并留痕）。见 §7.6 |

## 4. 非目标（明确不做）

- **不做原生对话 UI**：小程序不重写对话界面，`enableChunked` 流式对接不在范围内（那等于放弃 EmbedChat 的画布、工具面板、预览、浏览器面板）。
- **不做微信昵称/头像静默获取**：`wx.getUserProfile` 已被微信回收，静默拿到昵称在技术上不可能。头像昵称只能靠用户主动填写。
- **不做小程序内密码登录/切换账号**：静默登录即身份。
- **不改 `EmbedService`**、不改 EmbedChat 的 ticket 认证链路。
- **不种角色权限**：见 D3。
- **本期不做登录页的微信扫码登录，也不做「绑定已有账号」**（用户决定：微端上线后再评估）。独立绑定表（D13）届时可直接复用、无需返工——详见 §6.3。注意届时**不应**在扫码路径上自动开户：门户账号受审核体系约束（自助注册即 `status=2` 待审核），且须拒绝「小程序用户」角色的账号登录门户。
- **本期不做「微端账号自助设置登录名 + 密码」**（D14）：用户已确认这是紧接着要做的下一步，但因**不动表结构**而不阻塞微端上线，设计要点见 §6.4。
- **不改造 `quickstartFunctions`**：新增独立云函数，模板函数保持原样（便于对照与回退）。
- 不做支付、订阅、消息推送。

## 5. 端到端链路

```
微信小程序                                        NanZi 平台（★ = 本次新增）
────────                                        ──────────────────────────
① wx.cloud.callFunction('nanziSession')
      │
      └─ 云函数 nanziSession                          ★ 新增（仓库外工程）
           ├─ cloud.getWXContext() → OPENID/UNIONID   ← 微信注入，不可伪造
           └─ POST /api/v1/embed/miniprogram/session   ★ 需 API Key
                headers: X-API-Key: <云函数环境变量>
                body: { openid, unionid, appid, agent_id? }
                    │
                    ├─ [API Key 认证]（v1_secured 自带）
                    ├─ [权限] 显式校验 ★ 不能依赖 /embed 白名单（事实 7）
                    ├─ [开关] miniprogram_enabled == true     ★
                    ├─ [熔断] 每日新建账号上限（防雪崩，非风控）  ★
                    ├─ 查绑定 (appid,openid) → 回退 unionid    ★
                    │     命中 → user_id
                    │     未命中 → 建号 status=1 + 挂「小程序用户」角色
                    │                + 写绑定；明文 API Key 就地丢弃
                    ├─ 派生 instance_id = wx_<sha256(openid)[:16]> ★
                    └─ EmbedService.create_ticket(target_user_id)  ← 现有代码
      ◄── { ticket, expires_in, instance_id, user:{...} }
② web-view src = /embed/chat?ticket=emt_xxx&instance_id=wx_xxx#wechat_redirect
      └─ [EmbedChat] 现有逻辑兑换 ticket → emb_ses_* + embed_session Cookie
```

要点：

1. **ticket 在 web-view 打开之前签发**，web-view URL 由小程序构造。
2. **H5 认证零改动**：`/embed/chat?ticket=` 的兑换、并发去重、URL 清理、会话恢复（事实 1~3）全部复用。
3. **`instance_id` 由后端派生并回传**，不让小程序自行实现哈希：它决定会话分桶与本地存储键（`frontend/src/views/EmbedChat.vue:3302,4672`），必须逐用户隔离，写死会让所有微信用户共用一个分桶，撞上既有的跨用户会话拦截。
4. **openid 只信云函数**：平台不接收来自浏览器的 openid，接口必须持 API Key。

## 6. 身份与账号模型

### 6.1 绑定表（新增）

`ai_agent_wechat_bindings`

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | BIGINT | PK, autoincrement | |
| `user_id` | INT（与 `ai_agent_users.id` 同型） | NOT NULL, INDEX | 平台账号。**不加唯一约束**——同一账号可挂多个微信身份（多应用） |
| `appid` | VARCHAR(64) | NOT NULL | 微信应用 AppID（小程序 / 网站应用 / 公众号均可） |
| `openid` | VARCHAR(64) | NOT NULL | 该 AppID 下的用户标识（**逐应用不同**，见 §6.3） |
| `unionid` | VARCHAR(64) | NULL, INDEX | 开放平台统一标识，可空；跨应用关联靠它 |
| `created_at` | DATETIME/TIMESTAMP | NOT NULL | |
| `last_login_at` | DATETIME/TIMESTAMP | NULL | 便于运营观察 |

约束：`UNIQUE (appid, openid)`。

匹配顺序（三步）：

1. 按 `(appid, openid)` 查 → 命中即用该 `user_id`
2. 未命中且有 `unionid` → 按 `unionid` 查 → 命中则**新增一条绑定行**复用同一 `user_id`（支持同一微信在多个小程序/公众号间共享账号）
3. 仍未命中 → 建号，再写绑定

### 6.2 账号字段

| 字段 | 取值 | 理由 |
|---|---|---|
| `user_name` | `wx_` + `sha256(openid)[:16]` | 幂等稳定（同一 openid 恒等）、不泄露 openid、建后不可改（事实 11）。⚠️ **「幂等」不等于「无并发冲突」**：并发首次进入仍会撞 `user_name` 唯一键，建号路径必须捕获 `IntegrityError` 后重查绑定 |
| `real_name` | `微信用户`，可在原生首页自填昵称 | 静默拿不到昵称 |
| `password_hash` | `NULL` | 密码登录已被护栏拒绝（事实 9） |
| `status` | `1` | 免审核 |
| `role` | `user` | 系统角色只有这两个值（事实 12） |
| `role_ids` | `[「小程序用户」]` | 业务角色才是权限载体 |
| `extra_data` | 不写入 | 不用 JSON 字段承载身份绑定，避免无索引查询 |
| `api_key_*` | 由 `generate_api_key()` 正常生成 | **明文仅在进程内存在，立即丢弃**，绝不出现在接口响应或日志中 |

**API Key 处置是本设计的安全关键点**：`generate_api_key()` 必然签发一枚长期 Key（事实 10）。该 Key 的 `api_key_hash` 会落库并参与鉴权，所以「小程序用户」角色**不得授予任何 `api:` 权限**——否则一旦这枚 Key 以任何方式外泄，就成了一条绕过前端的 V1 接口通道。这同时是 D3「空角色」的安全红利。

> 注：建号复用 `AuthService.generate_api_key()` 是为了保证数据形态与现有用户一致（`api_key_encrypted`/`api_key_hash` 非空，避免后续管理员改密、重置 Key 等路径踩空），而非因为小程序需要 Key。

### 6.3 为什么用独立绑定表，而不在 `ai_agent_users` 上加列

微信官方 [UnionID 机制说明](https://developers.weixin.qq.com/doc/service/guide/product/unionid.html) 原文：

> **openid** 是微信用户对于一个应用（服务号）的身份标记，同一个微信用户**对不同应用（服务号）有不同的 openid**；
> **unionid** 是微信用户对于一个开放平台的身份标记。
> 速记公式：**微信用户 + 服务号 AppID = openid** / **微信用户 + 开放平台账号 = unionid**

即 **openid 是「用户 × 单个应用」，unionid 才是「用户 × 开放平台账号」**。由此：

- 同一个人在小程序、网站应用、公众号下会拿到**三个不同的 openid**，只有 unionid 相同；
- 若在用户表上加一列 `wechat_openid`，**最多只能存一个**——将来做网站应用扫码登录（D13 已确认为后续方向）时会直接卡死，只能再加列，此后每接一个微信入口就加一列；
- 独立绑定表天然表达「一个账号挂多行绑定、靠 unionid 串联」。

平台既有的风格同样是**按基数选载体**：一对一的 `dept_code` / `org_path`（组织架构同步）放在 `ai_agent_users` 上；多对多的用户↔角色用独立表 `ai_agent_user_role_relations`，而**没有**在用户表加 `role_ids` 列。微信身份属于后者。

**这张表不是「小程序的表」**，而是「微信身份 ↔ 平台账号」的通用映射层，同时服务于：微端自动开户（本期）、网站应用扫码登录（后续），以及同一微信身份在多个小程序/公众号间复用同一账号（§6.1 的 unionid 回退已支持）。

> **为什么不需要「绑定来源」字段**：本期不存在「用户主动绑定已有账号」这一操作——用户已明确该需求实为「**给自己的账号设置登录名**」（见 §6.4）。绑定表只有一种产生方式，加来源列没有信息量，故不设 `bind_source`。将来若真出现主动绑定/换绑场景再加（空表加列成本为 0）。

### 6.4 微端账号的 web 登录（D14，**暂缓**）

> **状态：暂缓**（用户 2026-10-15 决定：「改用户名先不做，后面再说」）。本节保留备查——下面「平台现有的能力盘点」与「前置检查」都是**核实过的事实**，将来重启该需求时不必重新调研。
>
> **当前零开发即可部分达成**：管理端已有 `POST /users/{user_id}/set-password`（`app/api/portal/endpoints/management.py:1044`，**无需旧密码**）。管理员给某个微端账号设个密码后，他就能用 `user_name`（`wx_<hash>`）+ 密码登录 web。唯一不足是这个名字不好记——而**解决「好记」正是改用户名的全部价值**，所以暂缓它等于接受这个体验现状。

**当初的目标**：让微端自动开户的账号能用「用户名 + 密码」登录 web，而不是被锁在微信里。注意这**不是**「绑定已有账号」——那个自动账号本身就是真实账号（有角色、配额、会话历史），只是缺一个人类可读的登录名和密码。

**平台现有的能力盘点**（核实后：真正缺的只有「改用户名」）：

| 能力 | 现状 |
|---|---|
| 设置/修改 `user_name` | ❌ **真正缺**。两条路都堵着：`PATCH /me/profile` 明确「只允许改邮箱」（`app/api/portal/endpoints/auth.py:1017`），管理端 `UpdateUserRequest` 也不含 `user_name` |
| 首次设置密码 | ✅ **底座已存在，可复用**。`POST /users/{user_id}/set-password`（`app/api/portal/endpoints/management.py:1044`）已实现「**无需旧密码**地设置密码」，内部三步：`AuthService.validate_password_complexity()`（等保复杂度）、`AuthService.set_user_password()`、`AuthService.revoke_sessions_for_user()`（改密后吊销全部会话）。用户自助路径只需换鉴权入口并复用这三步，**不要重写密码逻辑**，尤其别漏掉吊销会话 |
| 「授权」的平台既有形态 | ✅ 参考 `set-password` 的 `require_permission("element", "element:user:edit")`——即用 `element:*` 功能权限控制，与 §6.4 下方待澄清项 A/C 一致 |

**前置检查（必须，见 D15）**：只允许「从未产生业务引用」的账号设置登录名。因为 `user_name` 被这些表当作引用键：

- `agent.created_by = username`（`app/services/ai/agent_manager.py:971`）
- `knowledge.created_by = user_name`（`app/services/knowledge_base_service.py:48,83`）
- `slash_command.created_by = user_name`（`app/services/slash_command_service.py:84`）

而智能体可见性判断正是 `created_by == 用户名`，改名会让引用悬空、用户看不到自己创建的资源。微端账号因「小程序用户」是空角色（D3）而天然满足该条件，但**必须显式校验**，不能默认假定——否则管理员一旦给该角色放权，改名就会断链。

**落点只能在小程序内**：用户想上 web 设置用户名，但 web 登录本身就需要账号密码（鸡生蛋）。因此入口是小程序内的一个设置页：填用户名 + 密码 → 云函数带 openid 调平台新接口。该接口**必须**走已鉴权的云函数通道（API Key + 显式权限校验）——否则任何人都能给任意 openid 的账号设密码，等于送号。

**接口形态与授权（用户已定调）**：

1. **单独新增接口**——不塞进 `PATCH /me/profile`，也不改管理端 `UpdateUserRequest`。改用户名是敏感操作，必须与「改邮箱」这类自助资料编辑分开。
2. **只能改自己的**——接口**不接受「目标用户 ID」参数**，一律以调用者自身身份为准；**不提供**管理员代他人改名的入口。这从签名层面就杜绝了越权改掉别人登录名的可能。
3. **管理员审批**——本人提交后**不立即生效**，需管理员批准。

**由此产生四个必须一并设计的点（下一阶段动工前定）**：

- **审批请求落在哪**：平台现有的「待审核」是**用户级**状态（自助注册即 `status=2`），改名申请是另一种实体，**无法直接复用**。需要新建申请表（如 `ai_agent_username_change_requests`），字段至少含 `user_id` / `requested_user_name` / `status` / `created_at` / `reviewed_at` / `reviewed_by` / `reject_reason`。⚠️ **该表同样要出 MySQL + PG 两套迁移**。
  - 也可以选择**不持久化**（申请直接进 Redis 带 TTL 的待审队列），但管理员重启或超时后会丢申请、且无审计留痕，**不推荐**。
- **待审期间用哪个名字**：未批准前**保持原 `user_name` 不变**，批准时才改写——否则审批就失去意义。
- **审批界面**：管理端需要一个待审列表，可参考用户管理页「待审核」tab 的既有做法。
- **密码与用户名分开走**：建议**「设置密码」本人自助、立即生效**（密码是私有凭证，管理员不应参与、更不该看到），只有**改 `user_name`** 需要审批。二者可以是同一次表单提交，但落库与生效路径不同。

**不动的部分**：`ai_agent_users` 无需变更（`user_name` / `password_hash` 字段都已存在），`ai_agent_wechat_bindings` 也不需要新列。这也是它能排在微端之后、不阻塞上线的原因。

**一个设计红利**：因为身份索引在绑定表（D13），`user_name` 只是登录名/显示名——改名完全不影响微信识别（微端下次进来查的是 `(appid, openid)`，不是用户名）。建号时用的 `derive_user_name()` 只在「建号」这一路径上生效，不改名后的二次识别。

## 7. 平台侧改动

### 7.1 新增接口

`POST /api/v1/embed/miniprogram/session`（挂在 `app/api/v1/endpoints/embed.py` 的 `router`，即 `v1_secured` 之下，需 API Key）

请求（由云函数发出，**不面向浏览器**）：

```json
{ "openid": "...", "unionid": "...", "appid": "wx1ca87185956d0071", "agent_id": "可选" }
```

响应（`StandardResponse`）：

```json
{
  "data": {
    "ticket": "emt_...",
    "expires_in": 300,
    "instance_id": "wx_3f9a1c2b4d5e6f70",
    "user": { "user_id": 123, "user_name": "wx_3f9a...", "is_new": true }
  }
}
```

**权限校验（必须显式，且必须前置于建号）**：

- **复用现有权限码** `POST:/api/v1/embed/tickets`（权限页里的「代他人签发嵌入凭证」），**不新增权限码**、不改 `ASSIGNABLE_V1_API_RESOURCES`。语义本就吻合：本接口做的事正是"代他人签发嵌入凭证"，只是顺带建号。
- 接口自身要挂 `require_permission("api", "POST:/api/v1/embed/tickets")`，原因有二：
  1. 路径含 `/embed` 会被 `is_v1_api_whitelisted` 放行（事实 7），**自动检查根本不生效**；
  2. **更关键的是顺序**：`create_ticket` 内部也会检查这个权限码（事实 19），但那是**建号之后**才发生的——若不前置拦截，未授权调用者虽拿不到 ticket，却已经把账号**建出来了**，等于开放了一个刷号入口。
- 因此校验必须前置于 `resolve_or_create_user`。两处检查用同一个权限码，已授权调用不会互相打架。

- 不提供 `agent_id` 时，由用户在 EmbedChat 内从已授权智能体中选择。
- 响应**不含** API Key、openid、unionid。
- 失败语义：开关关闭 → 403；无权限 → 403；`openid` 缺失/格式非法 → 400；目标账号被禁用 → 403。（熔断触发只告警，不新增失败语义）

### 7.2 新增服务

`app/services/wechat_miniprogram_service.py`

- `resolve_or_create_user(openid, unionid, appid, db)`：实现 §6.1 三步匹配 + §6.2 建号。
- `derive_instance_id(openid)`：`wx_` + `sha256(openid)` 前 16 位十六进制。
- openid 格式校验：微信 openid 为 28 位 `[A-Za-z0-9_-]`，接口入口做长度与字符集校验，防注入与脏数据入库。
- **不实现 code2session**（D7）。

### 7.3 配置、凭证与开关

| 项 | 载体 | 默认 |
|---|---|---|
| `miniprogram_enabled` | `SystemConfig`（非敏感） | `false` |
| 平台 Base URL | **云函数环境变量** `NANZI_BASE_URL` | 空 |
| 云网关 API Key | **云函数环境变量** `NANZI_API_KEY` | 空 |
| 开户熔断阈值 | 平台代码内常量 | 纯防雪崩，**非风控**，见下 |

**本通路不做「防刷限流」，这是有意为之**：

- 接口不公开（需 API Key + 「代他人签发嵌入凭证」权限），唯一合法调用者是云函数，**不存在「公网匿名批量刷号」这一威胁**。
- 在 D7/D8 的模型下，限流的三个可用维度**全部失效**：
  - **按调用者（云函数）计数** = 给整个小程序设一个总流量上限，而每次进入聊天页都要签一次票，正常业务（日活 × 每人多次进入）会直接撞上；
  - **按 openid 计数无意义**：开户本身按 openid 幂等，同一 openid 只会建一次号；
  - **按 IP 计数不可得**：平台看到的是微信云函数的共享出口 IP，与真实用户无关。
- 平台现有的注册限流（`REGISTER_IP_LIMIT = 5`、`REGISTER_NAME_LIMIT = 3`，见 `app/services/auth_service.py:359-360`）**只是 `register` 端点内部的显式调用**，平台也**没有**全局限流中间件（`app/main.py` 只挂 GZip / AccessLog / CORS / SecurityHeaders），因此新通路**一点都继承不到**。

真正承担成本防线的是**角色配额**（D4）与**可审计性**（每笔开户记录 `created_by_user_id`），不是限流。

仅保留一个**高阈值熔断**（建议：每日新建账号 5000），目的只是「云函数出现 bug 时不要无限建号」，触发时**告警**而非静默拒绝。该值必须显著高于业务峰值，不能当风控用。

**平台不需要 AppSecret**（D9），因此 `env.example` **不新增**任何微信密钥项。

云网关账号（= 云函数在平台上的身份）：

概念上它**不是一个新机制**，而是把平台**现有的「宿主后端代客签票」信任模型**用在一个新宿主上。现有 `docs/md/embed_integration_guide.md` 的模型是「宿主后端持 API Key，代表 zhangsan 签发 ticket」；这里只是把宿主后端换成了**小程序云函数**，把「zhangsan」换成了「openid」。因此：

- 云函数 = 宿主后端；云网关 API Key = 宿主服务账号的 Key。
- 平台**信任持有该 Key 的调用者所声明的 openid**（openid 由微信注入云函数、不可伪造，但平台本身无法独立验证，故必须靠 Key 证明调用者身份）。

落地动作（全部由管理员手工完成，Key 不落迁移、不落仓库）：

1. 在后台「用户管理」新建一个普通账号（如 `miniprogram_gateway`），仅作服务身份，不用于登录或聊天。
2. 在权限页「外部 API」里**只**勾选 `POST:/api/v1/embed/tickets`（「代他人签发嵌入凭证」），不勾其它任何项。
3. 复制该账号的 API Key，填入云函数环境变量 `NANZI_API_KEY`。

为什么用**独立账号**而不是复用 admin 的 Key：`require_permission` 对 admin 直接放行，一旦泄露影响面是全平台；独立账号则权限最小、审计清晰、且 Key 可单独轮换（`reset-key`）而不影响任何人。

它**需要且只需要**权限页里的**一张卡**：`POST:/api/v1/embed/tickets`（「代他人签发嵌入凭证」）。这一张同时满足两处检查——接口的前置校验（§7.1）与 `create_ticket` 内部的代客签票护栏（事实 19）。**勾多了没必要，勾少了会 403。**

它**不需要**可见智能体（不聊天、不执行智能体），也**不勾**其它任何 API。

### 7.4 配置分层与「方便下次修改」

平台地址、网关账号、Key 都会变，因此明确分层：**能放平台侧的绝不放小程序侧，能放函数配置的绝不放代码里**。

| 配置 | 存放位置 | 谁改 | 改完的代价 |
|---|---|---|---|
| 平台地址 `NANZI_BASE_URL` | 云函数环境变量 | 运维 | 改**函数配置**，不需重新提审小程序 |
| 云网关 Key `NANZI_API_KEY` | 云函数环境变量 | 管理员（后台复制） | 同上 |
| 功能开关 `miniprogram_enabled` | 平台 `SystemConfig` | 管理员 | **立即生效，连云函数都不用碰** |
| 可见智能体 / 配额 | 「小程序用户」角色 | 管理员 | 立即生效 |
| **用哪个账号当网关** | 平台账号 + 「代他人签发嵌入凭证」权限 | 管理员 | **只需把该权限授给新账号 + 更新云函数 Key，代码零改动** |
| 超时 / 重试次数 | 云函数环境变量（可选） | 运维 | 同 Base URL |
| 欢迎页文案、默认 agent_id 等展示项 | 小程序前端代码 | 开发 | 需重新发版提审，故**只放展示性内容** |

约束（写入云函数实现约定）：

- 云函数**不得硬编码**平台地址与 Key，**也不得**放进随代码包一起上传的配置文件（`config.js` 之类）——那样改配置要重新传代码包，且 Key 极易误提交进 git。环境变量属于函数**配置**，改它不动代码包。
- 环境变量缺失时**必须明确报错**（返回可区分的错误码 + 日志），**不得内置任何默认 URL 兜底**，否则漏配会静默打到错误环境。
- 环境变量 key 需符合云开发命名限制（字母开头、仅 `[a-zA-Z0-9_]`），`NANZI_BASE_URL` / `NANZI_API_KEY` 均合规。
- 平台侧**代码不感知具体是哪个账号**：只校验权限码，因此换网关账号无需改任何代码（这也是"gateway 账号可配置"的实现方式）。

### 7.5 迁移

| 文件 | 内容 |
|---|---|
| `db-prod/V170-create_wechat_bindings.sql` | 建 `ai_agent_wechat_bindings`（MySQL：`ENGINE=InnoDB`、`utf8mb4`） |
| `db-prod/V171-seed_miniprogram_role_and_config.sql` | 种角色 + 开关配置 |
| `db-prod-pg/V71-create_wechat_bindings.sql` | 同上，PG 语法（`BIGSERIAL`/`TIMESTAMP`） |
| `db-prod-pg/V72-seed_miniprogram_role_and_config.sql` | 同上，PG 语法 |

幂等写法（`apply_sql.py` 无版本记录表，事实 16）：

- MySQL：`INSERT ... ON DUPLICATE KEY UPDATE`
- PostgreSQL：`INSERT ... ON CONFLICT (...) DO NOTHING`（沿用 `V1-align_system_config_seeds.sql`、`V5-register_example_search_tool.sql` 的既有写法）

角色种子（D3）：

```sql
-- code 是稳定引用键，代码里按 code 查，绝不硬编码自增 id
INSERT INTO ai_agent_roles (code, name, description)
VALUES ('miniprogram_user', '小程序用户', '微信小程序静默登录自动开户的用户，可见智能体与配额由管理员配置')
ON DUPLICATE KEY UPDATE name = VALUES(name), description = VALUES(description);
```

**不插入任何 `ai_agent_resource_permissions` 行**——事实 13 表明权限是白名单，空权限即「看不到任何智能体」，属 fail-safe 默认。

开关种子（与既有 `V64-add_embedchat_watermark_configs.sql` 同风格，`is_secret = 0`）：

```sql
-- MySQL
INSERT INTO system_configs (`key`, `value`, `description`, `category`, `is_secret`)
VALUES ('miniprogram_enabled', 'false', '是否开启微信小程序微端自动开户与签票 (true/false)', 'other', 0)
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- PostgreSQL
INSERT INTO "system_configs" ("key", "value", "description", "category", "is_secret")
VALUES ('miniprogram_enabled', 'false', '是否开启微信小程序微端自动开户与签票 (true/false)', 'other', FALSE)
ON CONFLICT ("key") DO NOTHING;
```

默认 `false`：迁移上线不等于功能开启，必须由管理员显式打开。

### 7.6 管理端展示（用户管理页）

微端跑起来后，运营与排查都需要「看得见」。以下都是平台既有用户管理页的延伸，**不属于微端核心链路**，故排在回归任务之后。

**（1）「用户列表」加微信标识**

`GET /api/portal/management/users` 每条 item 增加 `wechat_bound: bool`。实现上**不要逐行查**——在分页取到本页用户 ID 后，对绑定表做**一次** `IN` 查询得到 `set[user_id]`，避免 N+1。

**（2）新增「微信绑定」tab**

`frontend/src/views/Users.vue` 的 tab 是硬编码数组 + 联合类型（`activeView = ref<"list" | "review">("list")`、`switchView(view: "list" | "review")`），加第三个 tab 需同步改**四处**（tab 数组、ref 类型、`switchView` 参数类型、模板 `as` 断言）——漏改会被 `vue-tsc --noEmit` 抓住。

⚠️ `switchView` 内含 `statusFilter` 的进出场逻辑（进 review 设 `"2"`、离开还原 `""`），新 tab **必须**同样还原为 `""`，否则会污染用户列表的筛选状态。

数据形态：**一行 = 一条绑定记录**（不是一行一个用户——同一账号将来可能挂多个微信身份）。

| 列 | 说明 |
|---|---|
| 用户 | `user_name` + `#id` |
| 来源 AppID | 哪个小程序/应用绑的（未来多入口时用于分辨） |
| openid | **默认脱敏**：`oABC12****…****9012` |
| unionid | 同上，无则显示 `—` |
| 绑定时间 / 最后登录 | `created_at` / `last_login_at`，默认按最后登录倒序 |

**（3）openid 明文按需取，不随列表下发**

新增 `GET /api/portal/management/wechat-bindings/{binding_id}/identity` 单独返回完整 `openid`/`unionid`，供管理员对照云函数日志排查。**不**给列表接口加 `include_raw` 参数——那等于一次请求把整页明文全下发，脱敏就白做了。

**接口权限对照**：

| 接口 | 权限 |
|---|---|
| `GET /wechat-bindings` | `require_permission("menu", "menu:system:users")`（与 `GET /users` 同口径，查看级） |
| `GET /wechat-bindings/{id}/identity` | `require_permission("element", "element:user:edit")`（编辑级，更严）+ 结构化日志留痕 |

> 明文取用升到编辑级并留痕，是因为它能关联到具体微信用户。注意 openid **不是凭证**（拿它无法登录），所以这是「减少不必要暴露」而非「防止越权」。

## 8. 小程序侧（仓库外工程）

工程：`/Users/chenxiaolong/WeChatProjects/miniprogram-nanzi-ai`。**本仓库的实现计划不包含这些文件**，但接口契约（§7.1）与页面职责在此约定。

### 8.1 新增云函数 `nanziSession`

- 用 `cloud.getWXContext()` 取 `OPENID` / `UNIONID` / `APPID`（借鉴模板 `quickstartFunctions/index.js` 的 `getOpenId`，事实 2.3.3）。
- 用环境变量 `NANZI_BASE_URL` + `NANZI_API_KEY` 调 §7.1 接口（`axios` 或内置 `https`，依赖写入该云函数自己的 `package.json`）；**配置约定见 §7.4**（不得硬编码、不得放进随代码包上传的配置文件、缺失时必须明确报错）。
- **只回传** `ticket` / `expires_in` / `instance_id` / `user` 摘要；不回传 API Key、不打印完整响应到日志。
- 超时设 10s（首次调用含建号写库）。
- 前置依赖：**需先开通云开发环境**（`envList` 当前为空，事实 2.3.4）。

### 8.2 页面

| 页面 | 职责 |
|---|---|
| `pages/index/index` | 改写现有模板首页为原生首页：品牌展示、进入对话、可选「设置昵称」（`open-type="chooseAvatar"` + 昵称输入框，微信现行唯一允许方式）。用户已确认：**改成纯欢迎页也可以**，形态不限 |
| `pages/chat/chat` | **纯 `web-view`**：`onLoad` → `wx.cloud.callFunction('nanziSession')` → `setData({ webviewUrl })`。此页不得有任何其他 UI（事实 2.2.4） |
| `pages/file/file` | 原生文件处理：`wx.downloadFile` → `wx.openDocument`（pdf/doc/docx/xls/xlsx/ppt/pptx/txt）；图片走 `wx.saveImageToPhotosAlbum` |

- `pages/example/index`（模板页）可删除，并同步 `app.json` 的 `pages`。
- 聊天页必须在 `onLoad` 重新签票（ticket 一次性、5 分钟）；从后台切回若 `web-view` 被重建，同样重新签票。
- 签票失败要有原生重试界面，不能让用户停在白屏。
- `onShareAppMessage` 返回当前 `webViewUrl`，分享落地页由被分享者自行开户，不共享会话（`instance_id` 逐 openid 派生）。
- 域名配置：平台域名需配为**业务域名**（`web-view` 用）与 **downloadFile 合法域名**（原生文件页 `wx.downloadFile` 用，漏配会导致下载直接失败）；**不需要** request 合法域名（云函数调用属云函数出网、不受小程序 request 白名单约束）。

## 9. EmbedChat 适配（H5 侧）

全部改动都应局限在「检测到小程序宿主时才生效」的分支内，不影响浏览器/iframe 既有行为。

1. **环境检测**：`window.__wxjs_environment === 'miniprogram'`，UA 含 `miniProgram` 作兜底。
2. **iOS 白屏规避**：由小程序侧在 URL 末尾追加 `#wechat_redirect`；H5 侧保证参数无中文、必要时 `encodeURIComponent`。
3. **下载行为改写**：web-view 环境下不再触发 `<a download>`（会被微信拦截），改调 `wx.miniProgram.navigateTo('/pages/file/file?url=<encodeURIComponent(下载地址)>')`。这是**唯一即时**的 H5→小程序通道（事实 2.2.6）。
4. **凭证失效自救**：兑换失败或会话失效时，调 `wx.miniProgram.reLaunch('/pages/chat/chat?instance_id=<当前实例>')` 让小程序重新签票；`instance_id` 用于接回原会话。
5. **无可用智能体兜底**：`/api/portal/agents/allowed` 返回空时，展示「尚未开放智能体，请联系管理员」，而非空白或报错。
6. **不依赖 `postMessage`**：任何「通知小程序立即做某事」的逻辑都不得基于 `wx.miniProgram.postMessage`（事实 2.2.5）。

## 10. 边界与错误处理

| 场景 | 行为 |
|---|---|
| 开关关闭 | 接口 403；小程序显示「服务未开放」 |
| 调用者无权限 | 403（显式权限校验，§7.1） |
| `openid` 缺失/格式非法 | 400；不建号、不落库 |
| 平台接口不可达 | 云函数返回可区分的错误码；小程序提示稍后重试 |
| 新建账号熔断触发 | 记录告警日志，**不阻断请求**（§7.3：熔断是防雪崩，不是风控） |
| 用户被管理员禁用（`status=0`） | `create_ticket` 抛 `PermissionError`（事实 4）→ 403；小程序提示账号已停用 |
| ticket 未被兑换就过期 | 用户重进聊天页即重新签票，无感恢复 |
| `web-view` 被销毁重建 | 重新签票 + `?instance_id=` 接回会话 |
| 无可用智能体 | 兜底文案（§9.5） |
| 云开发环境未开通 / 云函数未部署 | 小程序侧调用失败，需原生提示，不能白屏 |
| 用户在 EmbedChat 内上传附件 | 走 `<input type="file">`；**无 `chooseMessageFile`**（事实 2.2.7），Android/iOS 行为不一致，需实机验证 |

## 11. 测试计划

### 后端

`tests/api/v1/test_miniprogram_session.py`（新增）

- 开关关闭 → 403；无 API Key → 401
- **权限**：持有效 API Key 但无 `POST:/api/v1/embed/tickets` 的账号 → 403，**且断言未产生任何新账号**（守护"校验先于建号"的顺序，§7.1）
- mock `resolve_or_create_user` 首次调用 → 建号、`status=1`、挂 `miniprogram_user` 角色、返回 ticket
- 同一 openid 二次调用 → **不重复建号**，`user_id` 不变，`is_new=false`
- 有 unionid 时：不同 appid 的同 unionid → 复用同一 `user_id` 并新增绑定行
- `openid` 缺失 / 非法字符集 / 超长 → 400，且**未产生任何新账号**
- 响应体**不含** `api_key` / openid / unionid（防回归断言）
- 签票目标正确：断言 `create_ticket` 收到的是 `target_user_id` 而非 `target_username`
- `instance_id` 稳定：同一 openid 多次调用返回同一 `instance_id`；不同 openid 不得碰撞
- 熔断：每日新建账号达阈值 → 触发告警，且**不得阻断已有账号的签票**（避免增长期误伤真实用户）
- 断言**不存在**按 IP 的开户限流逻辑（守护事实 18：平台看到的 IP 是云函数共享出口，无法区分真实用户）
- 目标用户 `status=0` → 403

`tests/test_miniprogram_migrations.py`（新增）

- 四个迁移文件均存在
- 两套 SQL 均含幂等写法（`ON DUPLICATE KEY UPDATE` / `ON CONFLICT`）
- MySQL 与 PG 的 `code` 值一致（`miniprogram_user`）
- 断言 SQL 中**不出现** `ai_agent_resource_permissions` 的插入（守护 D3）

`tests/test_v1_api_access_contract.py`（补充断言）

- 断言 `ASSIGNABLE_V1_API_RESOURCES` **仍为 4 项**（本设计不新增权限码，守护复用决策），且其中已含 `POST:/api/v1/embed/tickets`
- 记录 `/embed` 子串白名单行为存在（事实 7），即该接口**必须**自带显式权限校验

### 前端契约

`tests/frontend/test_embedchat_miniprogram_host_contract.py`（新增，沿用源码静态断言风格）

- EmbedChat 含小程序环境检测分支
- 下载路径在 web-view 分支下走 `wx.miniProgram.navigateTo`
- 含 `reLaunch` 重新签票自救
- 无可用智能体的兜底文案存在
- 断言**不存在**基于 `wx.miniProgram.postMessage` 的实时逻辑（守护事实 2.2.5）

### 迁移对齐

沿用 `tests/test_pg_prod_apply_sql.py` 的风格补充断言，确保两套迁移语义一致。

### 小程序端（仓库外，不在本仓库 pytest 范围）

以人工核对清单代替自动化测试：页面清单与 `app.json` 一致、聊天页无其他 UI 节点、文件页使用 `downloadFile`+`openDocument`、云函数不打印敏感响应。

## 12. 实施顺序

**本仓库（平台侧）**

1. 迁移：建表 + 角色/开关种子（两套），补迁移测试
2. 后端：绑定表模型 → `wechat_miniprogram_service` → 接口（显式权限**前置于建号**）+ 熔断告警 + 开关
3. 后端测试全绿
4. EmbedChat 适配 + 前端契约测试
5. 更新 `tests/CHECKLIST.md`

**仓库外（小程序工程，可并行）**

6. 开通云开发环境
7. 云函数 `nanziSession` + 环境变量
8. 三个页面（改写 index、新增 chat/file）
9. 微信后台配置业务域名
10. 实机联调

## 13. 上线前置检查清单

- [ ] 小程序为**企业/组织主体**（个人主体无法使用 `web-view`）
- [ ] 平台已部署在 **https + 已 ICP 备案**域名上（新备案需等待 24 小时）
- [ ] 该域名已在微信后台配置为**业务域名**（`web-view` 需要）
- [ ] 该域名已同时配置为 **downloadFile 合法域名**（原生文件页 `wx.downloadFile` 需要，漏配则下载失败）
- [ ] 云开发环境已创建、云函数已部署，且 `NANZI_BASE_URL` / `NANZI_API_KEY` 配在**函数环境变量**上（代码中无硬编码、无默认 URL 兜底，见 §7.4）
- [ ] 云网关账号已建，且**仅**授予 `POST:/api/v1/embed/tickets`（「代他人签发嵌入凭证」）一项 API 权限
- [ ] 「小程序用户」角色**未勾选任何「外部 API」**（否则自动开户用户手里的 API Key 会成为 V1 接口通道）
- [ ] `miniprogram_enabled = true`
- [ ] **已给「小程序用户」角色勾选可见智能体**（未勾选时用户进来看不到任何智能体）
- [ ] 已按需配置该角色的配额策略
- [ ] 云网关 API Key 未出现在小程序代码、仓库或 `SystemConfig` 中
- [ ] 实机验证：附件上传、文件下载、iOS 白屏、切后台恢复

## 14. 风险

1. **云函数的 Key 是新的信任根**：D10 的模型下，持有 `NANZI_API_KEY` 者可伪造任意 openid 开户。缓解：专用账号 + 单一权限码 + Key 只存云函数环境变量 + **平台侧审计与角色配额**（每笔开户可追溯到 `created_by_user_id`；成本由配额封顶）。注意**限流在此模型下不构成防护**（§7.3），所以 Key 保管是唯一有效手段。**这是本设计最需要守住的一处**。
2. **提审风险**：原生首页是缓解手段，但「纯网页套壳」的判定权在微信审核，**无法预先保证过审**。若被拒，备选是增加原生内容（如会话列表、消息通知）。
3. **备案等待**：域名若尚未备案，ICP 备案本身 + 配置前的 24 小时等待是排期上的硬阻塞。
4. **附件上传体验**：`<input type="file">` 在微信 `web-view` 内 Android/iOS 行为不一致，且无法使用 `chooseMessageFile`，可能需要降级为「原生页选文件后回传」。
5. **`web-view` 生命周期不可控**：页面被销毁重建的时机由微信决定，因此每次进入都必须能重新签票；任何依赖前端持久化的假设都要以 Cookie/sessionStorage 丢失为前提来设计。
6. **云开发依赖**：引入云开发后，小程序上线依赖该环境可用；若不愿长期绑定，可回退到「小程序传 code + 平台 code2session」方案（需补 AppSecret 与 request 合法域名），接口契约可保持不变、仅替换 openid 来源。
7. **web-view 内其它下载落点未适配（已知缺口，本期不修）**：`<a download>` / `blob:` 下载在微信 `web-view` 里会被拦截。本期只改了 `EmbedChat.vue` 内的两个落点，其余仍在：`frontend/src/utils/chatSessionExport.ts:142`（会话导出）、`utils/workspaceFilePreview.ts:231,307`、`components/embed/ChatCanvas.vue:133,144,157`、`components/embed/MessageRenderer.vue:363`、`components/embed/RagPreviewDrawer.vue:263`、`components/chatbi/ChatBIInsightPanel.vue:526`、`components/chatbi/SavedReportResultTable.vue:47`。⚠️ **这些多半给出的是 `blob:` 地址，本质上无法交给小程序文件页**——要么后端改为下发可访问直链（配合 downloadFile 合法域名），要么在小程序宿主内隐藏这些入口。这是设计问题，需下一阶段专门处理。
