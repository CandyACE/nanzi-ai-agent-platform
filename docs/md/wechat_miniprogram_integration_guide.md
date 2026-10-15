# NanZi智能体平台微信小程序微端集成指南 (WeChat Mini Program Integration Guide)

本文档指导如何把南孜 AI Agent 平台的对话能力**以微信小程序微端的形式**交付给用户：用户在小程序内**静默登录**，平台自动为其开设账号，并直接把 [`/embed/chat`](./embed_integration_guide.md) 嵌进小程序的 `web-view`。**用户全程不需要**注册、填手机号、设密码或任何登录表单。

本文档面向两类读者，请按需跳读：

| 你是 | 重点章节 |
| --- | --- |
| **平台管理员 / 运维** | [四、平台侧准备（管理员必做）](#四平台侧准备管理员必做)、[八、域名配置](#八域名配置) |
| **小程序开发者** | [三、集成架构与认证原理](#三集成架构与认证原理)、[五、接口契约](#五接口契约)、[六、云函数实现](#六云函数实现)、[七、小程序页面](#七小程序页面) |

> ⚠️ **重要：不要跳过第二章**。微端有**三条非代码的硬前提**（企业主体、ICP 备案、域名白名单），缺任何一条，代码写得再对也**跑不起来**。

---

## 目录 (Table of Contents)

1. [三条硬前提（缺一不可）](#一三条硬前提缺一不可)
2. [这是什么 / 适用场景](#二这是什么--适用场景)
3. [集成架构与认证原理](#三集成架构与认证原理)
4. [平台侧准备（管理员必做）](#四平台侧准备管理员必做)
5. [接口契约](#五接口契约)
6. [云函数实现](#六云函数实现)
7. [小程序页面](#七小程序页面)
8. [域名配置](#八域名配置)
9. [常见问题与排错指南 (FAQ & Troubleshooting)](#九常见问题与排错指南-faq--troubleshooting)
10. [已知限制](#十已知限制)

---

## 一、三条硬前提（缺一不可）

| # | 前提 | 说明 | 排期影响 |
| --- | --- | --- | --- |
| 1 | **小程序必须是企业/组织主体** | **个人主体的小程序不能使用 `web-view`**（微信明确限制）。微端整个方案建立在 `web-view` 之上，个人主体 = 方案走不通，需先做主体变更或重新注册 | 主体变更后 **AppID 可能改变 → 所有 openid 失效**（这正是必须采集 unionid 的原因） |
| 2 | **平台域名已完成 ICP 备案**，并配置为**业务域名** | 见[第八章](#八域名配置) | ⚠️ **新备案域名有 24 小时等待期**才能配置成功，请提前做 |
| 3 | **同一域名另配 `downloadFile` 合法域名** | 原生文件页下载文件需要它，这是**另一份独立白名单** | 配了业务域名 ≠ 配了 downloadFile 域名，**容易漏** |

---

## 二、这是什么 / 适用场景

### 1. 用户路径

```
微信打开小程序 → 静默拿到 openid（微信身份，不可伪造）
              → 云函数用它向平台换一张一次性 ticket
              → 小程序打开 web-view，URL 带 ticket
              → EmbedChat 用 ticket 换会话，用户开始对话
```

### 2. 为什么用 `web-view` 而不是重写原生界面

智能体对话界面（流式输出、图表、文件预览、知识库引用、会话历史等）已在 Web 端完成。用 `web-view` 直接复用**成本最低、也最不容易产生功能分叉**。代价是要接受微信对 `web-view` 的一系列限制（见[第十章](#十已知限制)）。

### 3. 身份模型（理解这一节，才能理解为什么要那张表）

| 概念 | 含义 |
| --- | --- |
| **openid** | **一个微信用户 × 一个小程序** 的唯一标识。**换 AppID 就全变** |
| **unionid** | **一个微信用户 × 一个开放平台账号** 的唯一标识。同一开放平台下的多个小程序/公众号共享 |

平台**不**依赖小程序传来的任何用户资料认人，而是：

1. 云函数用 `cloud.getWXContext()` 取 openid——该值由**微信运行时注入**，小程序前端**无法伪造**，也**不需要 AppSecret**；
2. 平台在**独立绑定表** `ai_agent_wechat_bindings` 里按 `(appid, openid)` 查：
   - **命中** → 取出对应平台账号，签发 ticket；
   - **未命中但 unionid 命中另一条绑定** → 同一微信在别的应用来过，**复用该账号**并补一条绑定行；
   - **都没命中** → 自动创建账号（账号名 = `wx_` + openid 摘要）并挂空的「小程序用户」角色。

> 💡 **为什么必须有这张绑定表**：一个看似更省事的做法是「不建表，下次用 openid 重新算出账号名，去用户表里查」。**这是错的**——账号名将来允许被修改，一旦用户把 `wx_3f9a...` 改成 `zhangsan`，下次用 openid 算出来的名字就查不到，平台会**再建一个新账号、他之前的对话历史全部"消失"**。所以**身份索引必须落在绑定表上**，账号名只是展示名。

**由此推出两条纪律**：

1. **能取到 unionid 就一定要带上**——将来换 AppID 时，openid 会全部失效，unionid 是**唯一**能把老用户捞回来的绳子；
2. **不要随意清理绑定表**——删一行 = 那个微信用户下次进来会变成"新用户"。

---

## 三、集成架构与认证原理

```
┌──────────────┐  ①cloud.getWXContext()
│ 小程序原生页  │──────────────┐
│ pages/index  │              ▼
└──────────────┘     ┌─────────────────┐
                     │ 云函数           │
                     │ nanziSession     │
                     └────────┬────────┘
                              │ ② POST /api/v1/embed/miniprogram/session
                              │    Header: X-API-Key: <云函数环境变量>
                              │    Body: {openid, appid, unionid}
                              ▼
                    ┌──────────────────────┐
                    │ NanZi 平台            │
                    │ ① 鉴权 + 权限校验      │
                    │ ② 按 openid 查/建账号  │
                    │ ③ 签发一次性 ticket    │
                    └──────────┬───────────┘
                              │ ③ {ticket, expires_in, instance_id, user}
                              ▼
                     ┌─────────────────┐
                     │ 云函数           │
                     │ 补上 base_url    │ ← 来自它自己的环境变量
                     └────────┬────────┘
                              │ ④ {ok, ticket, instance_id, base_url}
                              ▼
┌──────────────┐  ⑤ 拼 URL 并跳转
│ 小程序聊天页  │───────────────────────────────┐
│ pages/chat   │                               ▼
└──────────────┘              ┌──────────────────────────────────────────┐
   （纯 web-view）             │ {base_url}/embed/chat?ticket=emt_...      │
                              │            &instance_id=wx_...            │
                              │            #wechat_redirect               │
                              └──────────────┬───────────────────────────┘
                                             ▼
                                  ┌────────────────────┐
                                  │ EmbedChat 页面      │
                                  │ ⑥ ticket 换会话     │
                                  │ ⑦ 开始对话          │
                                  └────────────────────┘
```

**两条容易误读的设计**：

1. **长期 API Key 只存在于云函数环境变量**里；小程序前端与 URL 里**只有**一次性的、默认 5 分钟有效的 `ticket`。
2. **`base_url` 不是平台接口返回的**。平台只返回 `ticket` / `expires_in` / `instance_id` / `user`；`base_url` 由**云函数**从自己的环境变量 `NANZI_BASE_URL` 读出后补进返回值。这样**平台地址只配一处**，小程序侧零硬编码。

---

## 四、平台侧准备（管理员必做）

> 这三项**缺任何一项，小程序端都会失败**，且失败现象各不相同（见 FAQ Q1/Q2/Q4）。

### 1. 打开微端开关

进入 **系统配置 → 参数配置**，找到 `miniprogram_enabled`（**胶囊开关**，默认关闭），改为**开启**。

未开启时接口固定返回 `403`，信息为「微信小程序微端未开启」。

### 2. 建专用网关账号并授权

平台接口需要鉴权。请**新建一个专用账号**（不要复用管理员主账号），只授予一项权限：

| 权限项 | 资源 ID |
| --- | --- |
| 代他人签发嵌入凭证 | `POST:/api/v1/embed/tickets` |

然后用该账号生成 **API Key**，交给小程序云函数配置（**不要**写进小程序代码、不要提交仓库）。

> 💡 微端**不新增权限码**，复用的就是嵌入功能既有的「代他人签发嵌入凭证」。该权限要求**同时**满足：账号拥有它，且 `/embed` 路径不被细粒度权限拦截——平台侧已显式挂载校验，无需额外配置。

### 3. 给「小程序用户」角色勾选可见智能体

平台自动创建的账号会挂上固定角色 **`miniprogram_user`（「小程序用户」）**，该角色**初始为空、没有任何权限行**。

智能体的可见性是**白名单**——空角色 = 看不到任何智能体（这是刻意的 **fail-safe 默认**）。请到 **角色管理** 里给该角色勾选允许小程序用户使用的智能体。

> 若跳过这一步，用户登录后会看到兜底文案「尚未开放智能体，请联系管理员」。**这是设计行为，不是 bug。**

---

## 五、接口契约

### 1. 接口总览

| 项 | 值 |
| --- | --- |
| 方法 / 路径 | `POST /api/v1/embed/miniprogram/session` |
| 完整地址 | `{NANZI_BASE_URL}/api/v1/embed/miniprogram/session` |
| 调用方 | **微信云函数**（不要从小程序前端直接调） |
| 鉴权 | 请求头 `X-API-Key: <网关账号的 API Key>` |

### 2. 请求

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `openid` | string | ✅ | **必须来自 `cloud.getWXContext()`**，不要由前端传入 |
| `appid` | string | ✅ | 小程序 AppID，建议同样从 `getWXContext()` 取 |
| `unionid` | string | ⭕ | **能取到就一定要带上**（见[第二章](#3-身份模型理解这一节才能理解为什么要那张表)） |
| `agent_id` | string | ⭕ | 想锁定某个智能体时传；不传则由用户界面里自己选 |

```json
{
  "openid": "oABC1234567890123456789012",
  "appid": "wx1ca87185956d0071",
  "unionid": "oUvXxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

> ⚠️ **openid 格式校验**：平台校验其为 `16~64` 位的 `[A-Za-z0-9_-]`。微信生成的 openid 都满足；传空值或含空格/中文会返回 **400**。

### 3. 响应

**成功（200）**：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "ticket": "emt_1a2b3c4d5e6f...",
    "expires_in": 300,
    "instance_id": "wx_9cef4608ef468f15",
    "user": { "user_id": 24554, "user_name": "wx_9cef4608ef468f15", "is_new": true }
  }
}
```

| 字段 | 说明 |
| --- | --- |
| `data.ticket` | **一次性** ticket，默认 300s、最长 1800s；用掉即废（服务端原子核销） |
| `data.expires_in` | ticket 有效秒数 |
| `data.instance_id` | 前端会话实例标识（逐 openid 派生）。**必须**透传进 web-view URL，否则所有用户会共用同一个会话分桶 |
| `data.user.is_new` | 本次是否新建账号。可用于打点，**不要**用它做业务分支 |

> 🔒 响应里**不会**出现 `openid`、`unionid`、API Key 或密码哈希等敏感字段。

**失败**：

| HTTP | 触发条件 | 你该怎么处理 |
| --- | --- | --- |
| **400** | `openid` 缺失或格式非法 | 说明 `getWXContext()` 没取到值 → 检查云函数是否真在小程序环境里被调用 |
| **401 / 403** | 未带 API Key、Key 无效，或账号**缺少 `POST:/api/v1/embed/tickets`** | 检查环境变量与平台授权；错误信息会写明 `Permission required: ...` |
| **403** | 开关 `miniprogram_enabled` 未开启（「微信小程序微端未开启」） | 见[第四章第 1 节](#1-打开微端开关) |
| **403** | 该账号已被禁用 | 让管理员解禁 |
| **404** | 传了 `agent_id` 但该智能体不存在 | 去掉 `agent_id` 或换一个 |
| **500** | 平台内部错误 | 重试；持续失败查平台日志 |

### 4. 拿到 ticket 之后：自己拼 web-view URL

平台**不**返回可直接使用的 URL，由小程序自己拼：

```js
const url =
  base_url +                                   // 云函数从 NANZI_BASE_URL 环境变量带回来
  '/embed/chat' +
  '?ticket=' + encodeURIComponent(ticket) +
  (instance_id ? '&instance_id=' + encodeURIComponent(instance_id) : '') +
  '#wechat_redirect'
```

| 要求 | 原因 |
| --- | --- |
| **必须带 `instance_id`** | 它决定会话分桶与本地存储键，漏了会让所有用户共用一份会话 |
| **URL 不得含中文** | 微信对 web-view 的 URL 有编码要求，务必 `encodeURIComponent` |
| `#wechat_redirect` 后缀**建议保留** | 规避 iOS 下 JSSDK 无响应的问题 |

---

## 六、云函数实现

### 1. 环境变量（在云开发控制台配置）

| 变量 | 说明 |
| --- | --- |
| `NANZI_BASE_URL` | 平台地址，如 `https://your-domain.com`（**不要**以 `/` 结尾） |
| `NANZI_API_KEY` | 第四章第 2 节生成的网关账号 API Key |

> ⚠️ **本地调试读不到**云函数环境变量，必须在控制台配置**并重新部署**才生效。另外**不要**给 Key 兜底默认值——没配就直接报错，别退化成某个硬编码地址。

### 2. 云函数 `nanziSession`

```js
const cloud = require('wx-server-sdk')
const https = require('https')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

// 极简 POST；生产建议换成 axios/got 并加 8~10s 超时
function postJson(url, body, headers) {
  return new Promise((resolve, reject) => {
    const u = new URL(url)
    const payload = JSON.stringify(body)
    const req = https.request(
      {
        hostname: u.hostname,
        port: u.port || 443,
        path: u.pathname + u.search,
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload), ...headers },
        timeout: 10000,
      },
      (res) => {
        let raw = ''
        res.on('data', (c) => (raw += c))
        res.on('end', () => {
          let parsed = null
          try { parsed = JSON.parse(raw) } catch (e) { /* 保留 raw 供排查 */ }
          resolve({ status: res.statusCode, body: parsed, raw })
        })
      }
    )
    req.on('timeout', () => req.destroy(new Error('timeout')))
    req.on('error', reject)
    req.write(payload)
    req.end()
  })
}

exports.main = async () => {
  // ① openid/unionid/appid 只能从这里取：微信运行时注入，不可伪造
  const { OPENID, UNIONID, APPID } = cloud.getWXContext()

  if (!OPENID) {
    return { ok: false, message: '未能获取微信身份，请在小程序内打开' }
  }

  const baseUrl = process.env.NANZI_BASE_URL
  const apiKey = process.env.NANZI_API_KEY
  if (!baseUrl || !apiKey) {
    // 明确报错，不要静默降级到硬编码地址
    console.error('[nanziSession] 未配置 NANZI_BASE_URL / NANZI_API_KEY')
    return { ok: false, message: '服务未配置，请联系管理员' }
  }

  try {
    // ② 带网关 Key 向平台换一次性 ticket
    const resp = await postJson(
      `${baseUrl}/api/v1/embed/miniprogram/session`,
      { openid: OPENID, appid: APPID, unionid: UNIONID || undefined },
      { 'X-API-Key': apiKey }
    )

    if (resp.status !== 200 || !resp.body || resp.body.code !== 200) {
      console.error('[nanziSession] 平台返回异常', resp.status, resp.raw)
      const msg =
        resp.status === 403 ? '微端未开启或未授权，请联系管理员' : '服务暂不可用，请稍后重试'
      return { ok: false, message: msg }
    }

    const data = resp.body.data || {}
    // ③ base_url 由云函数补上：平台地址只配一处，小程序侧零硬编码
    return {
      ok: true,
      ticket: data.ticket,
      instance_id: data.instance_id,
      base_url: baseUrl,
    }
  } catch (e) {
    console.error('[nanziSession] 调用失败', e)
    return { ok: false, message: '网络异常，请稍后重试' }
  }
}
```

**要点**：

| 要点 | 说明 |
| --- | --- |
| openid 只能从 `getWXContext()` 取 | 前端 `wx.login()` 拿到的 `code` 换不到 openid（那需要 AppSecret），所以**必须**走云函数 |
| `APPID` 也从 context 取 | 不要硬编码 |
| **API Key 绝不外泄** | 只放环境变量；不要 `console.log`；不要进小程序代码或仓库 |
| 不要拿到 200 后重复调用 | 会白白浪费 ticket |
| 返回值**不含** API Key | 只回传 `ticket` / `instance_id` / `base_url` |

---

## 七、小程序页面

### 1. 页面构成

| 页面 | 性质 | 职责 |
| --- | --- | --- |
| `pages/index/index` | 原生 | 欢迎页；点击进入聊天页 |
| `pages/chat/chat` | **纯 `web-view`** | 调云函数签票 → 拼 URL → 承载 EmbedChat |
| `pages/file/file` | 原生 | 承接 H5 的下载/预览请求（`wx.downloadFile` + `wx.openDocument`） |

### 2. 聊天页的两个硬约束

1. **一个页面只能有一个 `web-view`**，且它会**自动铺满整个页面**、覆盖其它组件。因此 loading / error 状态必须与 web-view **互斥渲染**（`wx:if` / `wx:else`），**不能叠加**。
2. **页面生命周期不可控**——销毁重建的时机由微信决定。任何"只做一次初始化"的假设，都要以**每次进入都重新签票**为前提。

### 3. 签票并跳转（核心逻辑）

```js
requestTicket() {
  this.setData({ loading: true, error: '' })
  wx.cloud.callFunction({ name: 'nanziSession', data: {} })
    .then((res) => {
      const r = (res && res.result) || {}
      if (!r.ok) {
        this.setData({ loading: false, error: r.message || '服务暂不可用' })
        return
      }
      const url =
        r.base_url +
        '/embed/chat' +
        '?ticket=' + encodeURIComponent(r.ticket) +
        (r.instance_id ? '&instance_id=' + encodeURIComponent(r.instance_id) : '') +
        '#wechat_redirect'
      this.setData({ webviewUrl: url, loading: false })
    })
    .catch(() => this.setData({ loading: false, error: '网络异常，请稍后重试' }))
}
```

### 4. H5 ↔ 小程序的通信（最容易设计错的地方）

> ⚠️ **`wx.miniProgram.postMessage` 没有实时性**：它发出的消息只在小程序**后退、组件销毁、分享、复制链接**时**批量**触发 `bind:message`。**不要**用它做「H5 通知小程序立刻做某事」。

**唯一的即时通道是 `wx.miniProgram.*` 导航**：

| API | 效果 |
| --- | --- |
| `wx.miniProgram.navigateTo({url})` | 立刻跳转 |
| `wx.miniProgram.navigateBack()` | 立刻返回 |
| `wx.miniProgram.reLaunch({url})` | 立刻重启到某页 |

平台侧 EmbedChat 已用这个机制（**全部 gate 在宿主判断上，普通浏览器行为零变化**）：

- **H5 里点下载** → `navigateTo` 到 `pages/file/file`
- **凭证失效** → `reLaunch` 回 `pages/chat/chat` 重新签票（避免停在白屏）

**宿主检测**（平台侧用的就是这个）：

```js
window.__wxjs_environment === 'miniprogram' || /miniProgram/i.test(navigator.userAgent)
```

---

## 八、域名配置

> 路径：**微信公众平台 → 开发 → 开发管理 → 开发设置**。两份白名单**互相独立**，都要配。

| 配置项 | 用途 | 要求 |
| --- | --- | --- |
| **业务域名** | `web-view` 只能加载业务域名下的页面 | **https** + 域名**已完成 ICP 备案** + 下载微信校验文件放到域名根目录验证归属；⚠️ **新备案域名有 24 小时等待期** |
| **服务器域名 → `downloadFile` 合法域名** | 原生文件页用 `wx.downloadFile` 下载文件 | 同一域名也要配进来，**容易漏** |

**上线前检查清单**：

- [ ] 小程序主体为**企业/组织**，且已确认 `web-view` 可用
- [ ] 平台域名已 **ICP 备案**
- [ ] 平台域名已配 **业务域名**（并等过 24 小时生效期）
- [ ] 同一域名已配 **`downloadFile` 合法域名**
- [ ] 云开发环境已创建，云函数已部署，`NANZI_BASE_URL` / `NANZI_API_KEY` 已配
- [ ] 平台侧：`miniprogram_enabled` 已开启、网关账号已授权、「小程序用户」角色已勾选可见智能体
- [ ] **真机**（不是模拟器）走通：欢迎页 → 聊天页 → 能正常对话
- [ ] 真机验证下载：H5 里点导出 → 跳原生文件页 → 能下载/预览
- [ ] 真机验证异常路径：会话失效后重进能自动恢复

---

## 九、常见问题与排错指南 (FAQ & Troubleshooting)

### Q1: 云函数返回「微端未开启或未授权」，怎么定位？

先看**平台返回的具体信息**（云函数日志里有原始响应）：

| 平台信息 | 原因 | 处理 |
| --- | --- | --- |
| 「微信小程序微端未开启」 | 开关未打开 | [第四章第 1 节](#1-打开微端开关) |
| 含 `Permission required` | 网关账号**缺少 `POST:/api/v1/embed/tickets`** | [第四章第 2 节](#2-建专用网关账号并授权) |
| 其他 403 | 账号被禁用 | 让管理员解禁 |

### Q2: 云函数报「未配置 NANZI_BASE_URL / NANZI_API_KEY」？

环境变量没配，或**配了但没有重新部署**云函数。注意**本地调试读不到**云函数环境变量——这是微信的限制，不是配错了。

### Q3: 用户进去看到「尚未开放智能体，请联系管理员」？

平台管理员还没给「小程序用户」角色勾选可见智能体。**这是 fail-safe 设计，不是 bug**（见[第四章第 3 节](#3-给小程序用户角色勾选可见智能体)）。

### Q4: 所有用户看到**同一份**会话历史？

`instance_id` 没有透传进 web-view URL（见[第五章第 4 节](#4-拿到-ticket-之后自己拼-web-view-url)）。

### Q5: 用户重进变成新账号、历史记录没了？

两个可能：

1. 传给平台的 `openid` **不稳定**（例如错误地传了前端拿到的值，而非 `cloud.getWXContext()` 的）；
2. **绑定表被清理过**——删一行 = 该用户下次进来就是"新用户"（见[第二章第 3 节](#3-身份模型理解这一节才能理解为什么要那张表)）。

### Q6: `web-view` 打开一片空白 / 提示"无法打开"?

按顺序排查：

1. 域名**没配进业务域名**（或配了但 24 小时等待期未过）；
2. 页面**不是 https**；
3. URL 里**含中文**未编码。

### Q7: 用户在 H5 里点下载没反应？

- 若该入口是平台**已适配**的两处（对话导出、ChatBI 简报） → 应跳到原生文件页；检查 `downloadFile` 合法域名是否配了；
- 若是**其它**下载入口 → 见[第十章](#十已知限制)，本期**未适配**。

### Q8: 想换一个小程序 AppID，老用户怎么办？

openid 会**全部失效**。此时**只有 unionid 能救**——前提是历史绑定行里存过 unionid（这就是"能取到就一定要带上"的原因）。若没存过，老用户会全部变成新账号。

---

## 十、已知限制

| 限制 | 影响 / 说明 |
| --- | --- |
| **个人主体不能用 `web-view`** | 见[第一章](#一三条硬前提缺一不可) |
| **`web-view` 内 7 处下载落点未适配** | 会话导出、工作区文件预览、画布、消息渲染、RAG 预览、ChatBI 报表等入口，多为 `blob:` 地址，**本质上无法**交给小程序文件页，需后端下发直链或在小程序宿主内隐藏入口 |
| `<input type="file">` 在 `web-view` 内行为不一致 | Android/iOS 表现不同，且**无法**使用小程序的 `chooseMessageFile` |
| **纯网页套壳的审核风险** | 微信审核对「套壳」有裁量权，**无法预先保证过审**。本方案用**原生欢迎页**缓解；若仍被拒，备选是增加原生内容（如会话列表、消息通知） |
| 微端账号**暂不支持网页版登录** | 本期未做。管理员可用既有的「代设密码」接口为其设置密码后登录 web |
| **云函数出口 IP 共享** | 因此平台**刻意不做限流**（按 openid 计数无意义）；建号达 5000/日仅告警不阻断 |

---

## 相关文档

| 文档 | 内容 |
| --- | --- |
| [嵌入式组件集成指南](./embed_integration_guide.md) | EmbedChat / EmbedPersonal 的通用集成方式（Ticket 接口、多语言示例、PostMessage 协议、主题定制） |
| [API 集成指南](./api_integration_guide.md) | 平台 HTTP API 的通用接入方式 |
