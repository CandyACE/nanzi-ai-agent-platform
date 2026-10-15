# 小程序微端（微信小程序工程侧）实施计划

> **执行方式：** 本计划作用于仓库外工程，全部为人工/真机步骤。⚠️ 本环境**没有** `subagent-driven-development` / `executing-plans` 这两个 skill，不要尝试调用。步骤用 `- [ ]` 勾选跟踪。

**Goal:** 在微信小程序工程里落地微端：一个云函数取不可伪造的 openid 换 ticket，一个纯 `web-view` 聊天页承载 EmbedChat，一个原生文件页处理下载/预览。

**Architecture:** 云函数 `nanziSession` 用 `cloud.getWXContext()` 拿 openid → 调平台受保护接口 → 拿回 `ticket` + `instance_id` + **`base_url`**。**平台地址只配一处**（云函数环境变量），小程序侧零硬编码。聊天页必须是纯 `web-view` 页（微信规定一个页面只能有一个 web-view，且会自动铺满、覆盖其它组件），因此 loading/error 状态必须与 web-view **互斥渲染**。

**Tech Stack:** 微信小程序原生（JS/WXML/WXSS）+ 微信云开发（云函数 Node.js）+ `wx-server-sdk`

**⚠️ 本计划作用于仓库外工程：**
`/Users/chenxiaolong/WeChatProjects/miniprogram-nanzi-ai`（**不是** NanZi 平台仓库）

**配套计划（平台侧）：** `docs/superpowers/plans/2026-10-15-miniprogram-platform-side.md`（在平台仓库中）

**Spec:** `docs/superpowers/specs/2026-10-15-miniprogram-embedchat-design.md`（在平台仓库中）

---

## 执行前必读

1. **不要执行 `git commit`**（团队规范）。每个任务末尾的「检查点」只汇报改动与验证结果。
2. **本工程无法用平台仓库的 pytest 验证**。所有验证靠：微信开发者工具编译 + **真机预览**。
3. **三个硬前提**（不在代码里，缺一个就跑不起来）：
   - 小程序为**企业/组织主体**（个人主体**不支持** `web-view`，[官方限制](https://developers.weixin.qq.com/miniprogram/dev/component/web-view.html)）；
   - 平台域名已 **ICP 备案** + 配为**业务域名**（新备案需等 24 小时）；
   - 平台域名另配 **downloadFile 合法域名**（文件页 `wx.downloadFile` 需要它）。
4. **`postMessage` 不可用于实时通信**：`wx.miniProgram.postMessage` / `bind:message` 只在**小程序后退、组件销毁、分享、复制链接**时批量触发。任何"通知小程序立刻做某事"的逻辑都要用 `wx.miniProgram.navigateTo` / `reLaunch`（唯一即时通道）。
5. 本工程现状：`miniprogram/envList.js` 的 `envList` 为**空数组**（云开发环境尚未创建）；`app.json` 只有模板页 `pages/index/index`、`pages/example/index`；`cloudfunctions/` 下只有模板函数 `quickstartFunctions`（**不要改它**，留着对照）。

---

### Task 1: 开通云开发环境并接通 `wx.cloud.init`

**Files:**
- Modify: `miniprogram/app.js`
- Modify: `miniprogram/envList.js`

- [ ] **Step 1: 在微信开发者工具里开通云开发**

打开工程 → 点顶部「云开发」→ 按引导创建环境（如命名 `nanzi-prod`）→ 记下**环境 ID**（形如 `nanzi-prod-1a2b3c`）。

这一步必须在工具里手动完成，命令行无法替代。

- [ ] **Step 2: 填入环境 ID**

编辑 `miniprogram/envList.js`，把环境 ID 填进数组（替换 `const envList = []` 为实际值）：

```js
const envList = [
  {
    envId: 'nanzi-prod-1a2b3c',
    alias: 'NanZi 正式环境',
  },
]

module.exports = { envList }
```

（`envId` 换成 Step 1 里记下的真实值。）

- [ ] **Step 3: 确认 app.js 已初始化云开发**

读 `miniprogram/app.js`，确认 `onLaunch` 里有云开发初始化。若没有，加进去：

```js
const { envList } = require('./envList')

App({
  onLaunch() {
    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力')
      return
    }
    wx.cloud.init({
      env: envList.length ? envList[0].envId : wx.cloud.DYNAMIC_CURRENT_ENV,
      traceUser: true,
    })
  },
  globalData: {},
})
```

- [ ] **Step 4: 验证**

Run: 在微信开发者工具点「编译」

Expected: 编译无报错；「云开发」控制台能看到刚创建的环境。

- [ ] **Step 5: 检查点（不提交）**

汇报：环境 ID、`envList.js` 与 `app.js` 的最终内容、编译结果。

---

### Task 2: 云函数 `nanziSession`

**Files:**
- Create: `cloudfunctions/nanziSession/index.js`
- Create: `cloudfunctions/nanziSession/package.json`

**关键约定（来自 spec §7.4）：** 平台地址与 API Key **只能**来自云函数环境变量，**不得硬编码**、**不得**放进随代码包上传的配置文件（那样改配置要重传代码包，且 Key 极易误提交进 git）。环境变量缺失时必须**明确报错**，不许内置默认 URL 兜底。

- [ ] **Step 1: 写云函数入口**

创建 `cloudfunctions/nanziSession/index.js`：

```js
/**
 * nanziSession：为小程序微端换取 embed ticket。
 *
 * 信任链：微信运行时把 OPENID/UNIONID/APPID 注入云函数（调用方无法伪造），
 * 云函数再带平台 API Key 调平台受保护接口。
 *
 * 配置（云函数环境变量，不得硬编码）：
 *   NANZI_BASE_URL    平台地址，如 https://ai.example.com
 *   NANZI_API_KEY     云网关账号的 API Key（只授「代他人签发嵌入凭证」一项权限）
 *   NANZI_TIMEOUT_MS  可选，默认 10000
 */
const cloud = require('wx-server-sdk')
const https = require('https')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const TIMEOUT_MS = parseInt(process.env.NANZI_TIMEOUT_MS || '10000', 10)
const SESSION_PATH = '/api/v1/embed/miniprogram/session'

function postJson(targetUrl, body, headers) {
  return new Promise((resolve, reject) => {
    const u = new URL(targetUrl)
    const payload = JSON.stringify(body)
    const req = https.request(
      {
        hostname: u.hostname,
        port: u.port || 443,
        path: u.pathname + u.search,
        method: 'POST',
        headers: Object.assign(
          {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload),
          },
          headers
        ),
        timeout: TIMEOUT_MS,
      },
      (res) => {
        let raw = ''
        res.on('data', (chunk) => (raw += chunk))
        res.on('end', () => {
          let parsed = null
          try {
            parsed = JSON.parse(raw)
          } catch (e) {
            parsed = null
          }
          resolve({ statusCode: res.statusCode, body: parsed })
        })
      }
    )
    req.on('timeout', () => req.destroy(new Error('请求平台超时')))
    req.on('error', reject)
    req.write(payload)
    req.end()
  })
}

exports.main = async (event) => {
  const baseUrl = process.env.NANZI_BASE_URL
  const apiKey = process.env.NANZI_API_KEY

  // 缺配置必须明确报错，绝不内置默认地址兜底（否则漏配会静默打到错误环境）
  if (!baseUrl || !apiKey) {
    return {
      ok: false,
      code: 'CONFIG_MISSING',
      message: '云函数未配置 NANZI_BASE_URL 或 NANZI_API_KEY',
    }
  }

  const { OPENID, UNIONID, APPID } = cloud.getWXContext()
  if (!OPENID) {
    return { ok: false, code: 'NO_OPENID', message: '未能取得微信身份' }
  }

  const endpoint = baseUrl.replace(/\/+$/, '') + SESSION_PATH

  try {
    const res = await postJson(
      endpoint,
      {
        openid: OPENID,
        unionid: UNIONID || null,
        appid: APPID,
        agent_id: (event && event.agent_id) || null,
      },
      { 'X-API-Key': apiKey }
    )

    if (res.statusCode !== 200 || !res.body || !res.body.data) {
      // 只回传可安全暴露的信息；不回传 API Key、不回传完整响应
      return {
        ok: false,
        code: 'HTTP_' + res.statusCode,
        message: (res.body && res.body.detail) || '平台返回异常',
      }
    }

    const d = res.body.data
    return {
      ok: true,
      // 平台地址随票据一起下发，使小程序侧零硬编码（改地址只改云函数环境变量）
      base_url: baseUrl.replace(/\/+$/, ''),
      ticket: d.ticket,
      expires_in: d.expires_in,
      instance_id: d.instance_id,
      user: d.user,
    }
  } catch (err) {
    console.error('nanziSession 调用平台失败:', err.message)
    return { ok: false, code: 'REQUEST_FAILED', message: err.message }
  }
}
```

- [ ] **Step 2: 写依赖声明**

创建 `cloudfunctions/nanziSession/package.json`：

```json
{
  "name": "nanziSession",
  "version": "1.0.0",
  "description": "为小程序微端按 openid 换取 embed ticket",
  "main": "index.js",
  "dependencies": {
    "wx-server-sdk": "~2.4.0"
  }
}
```

（用内置 `https` 模块发请求，**不引入 axios**，少一个依赖。）

- [ ] **Step 3: 在云开发控制台配置环境变量**

云开发控制台 → 云函数 → `nanziSession` → 配置 → 环境变量，添加：

| Key | Value |
|---|---|
| `NANZI_BASE_URL` | 平台地址，如 `https://ai.example.com` |
| `NANZI_API_KEY` | 云网关账号的 API Key |

（Key 命名符合云开发限制：字母开头、仅 `[a-zA-Z0-9_]`。）

- [ ] **Step 4: 上传并部署云函数**

在开发者工具里右键 `cloudfunctions/nanziSession` → 「上传并部署：云端安装依赖」。

- [ ] **Step 5: 在控制台测试云函数**

云开发控制台 → 云函数 → `nanziSession` → 「云端测试」，用空事件 `{}` 调用。

Expected（二选一）：
- 返回 `{ ok: true, ticket: "emt_...", instance_id: "wx_...", base_url: "..." }` —— 说明全链路通了；
- 返回 `{ ok: false, code: "CONFIG_MISSING" }` —— 环境变量没配好，回到 Step 3；
- 返回 `{ ok: false, code: "HTTP_403" }` —— 平台侧开关未开（`miniprogram_enabled`）或权限未配，回到平台侧计划检查 Task 2/§13 清单。

注意：`cloud.getWXContext()` 在控制台「云端测试」里可能拿不到真实 OPENID。**这一步主要验证配置与网络连通性**，真实 openid 要靠 Step 6 真机验证。

- [ ] **Step 6: 真机验证**

在 `pages/index/index` 里临时加一个按钮调 `wx.cloud.callFunction({ name: 'nanziSession' })`，用**真机预览**点击，看返回是否有 `ticket`。

Expected: 真机返回 `ok: true` 且 `ticket` 以 `emt_` 开头。（Task 5 会用正式的聊天页替换这个临时按钮。）

- [ ] **Step 7: 检查点（不提交）**

汇报：云函数文件、环境变量清单（**不要写出 Key 的值**）、云端测试与真机测试的结果。

---

### Task 3: 聊天页 `pages/chat/chat`（纯 web-view）

**Files:**
- Create: `miniprogram/pages/chat/chat.js`
- Create: `miniprogram/pages/chat/chat.wxml`
- Create: `miniprogram/pages/chat/chat.wxss`
- Create: `miniprogram/pages/chat/chat.json`

**硬约束：**「每个页面只能有一个 `web-view`，会自动铺满整个页面，并覆盖其他组件」。所以 loading / error 状态必须与 `web-view` **互斥渲染**（`wx:if` / `wx:elif` / `wx:else`），不能叠加。

- [ ] **Step 1: 写页面逻辑**

创建 `miniprogram/pages/chat/chat.js`：

```js
Page({
  data: {
    webviewUrl: '',
    loading: true,
    error: '',
  },

  onLoad(options) {
    // 从原生文件页返回时可能带回 instance_id，用于接回同一会话
    this.instanceId = (options && options.instance_id) || ''
    this.requestTicket()
  },

  onShow() {
    // web-view 被销毁重建时不保留内容，因此没拿到 URL 就要重新签票
    if (!this.data.webviewUrl) {
      this.requestTicket()
    }
  },

  onShareAppMessage() {
    // 分享落地页由被分享者自行开户，不共享会话（instance_id 逐 openid 派生）
    return {
      title: 'NanZi 智能体',
      path: '/pages/index/index',
    }
  },

  requestTicket() {
    this.setData({ loading: true, error: '' })

    wx.cloud.callFunction({ name: 'nanziSession', data: {} })
      .then((res) => {
        const r = (res && res.result) || {}
        if (!r.ok) {
          this.setData({ loading: false, error: r.message || '服务暂不可用' })
          return
        }

        // iOS 下 JSSDK 无响应可在 src 后加 #wechat_redirect；URL 不得含中文
        const url =
          r.base_url +
          '/embed/chat' +
          '?ticket=' + encodeURIComponent(r.ticket) +
          (r.instance_id ? '&instance_id=' + encodeURIComponent(r.instance_id) : '') +
          '#wechat_redirect'

        this.setData({ webviewUrl: url, loading: false })
      })
      .catch(() => {
        this.setData({ loading: false, error: '网络异常，请稍后重试' })
      })
  },

  onRetry() {
    this.requestTicket()
  },
})
```

- [ ] **Step 2: 写页面结构**

创建 `miniprogram/pages/chat/chat.wxml`：

```xml
<!-- web-view 会铺满并覆盖其他组件，所以三种状态必须互斥渲染 -->
<view wx:if="{{error}}" class="state">
  <text class="state-title">暂时无法进入</text>
  <text class="state-desc">{{error}}</text>
  <button class="state-btn" bindtap="onRetry">重试</button>
</view>

<view wx:elif="{{loading}}" class="state">
  <text class="state-title">正在进入…</text>
</view>

<web-view wx:else src="{{webviewUrl}}"></web-view>
```

- [ ] **Step 3: 写样式**

创建 `miniprogram/pages/chat/chat.wxss`：

```css
.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  padding: 0 48rpx;
  box-sizing: border-box;
}

.state-title {
  font-size: 34rpx;
  color: #1f2937;
  margin-bottom: 16rpx;
}

.state-desc {
  font-size: 28rpx;
  color: #6b7280;
  text-align: center;
  line-height: 1.6;
}

.state-btn {
  margin-top: 40rpx;
  background-color: #2563eb;
  color: #ffffff;
  font-size: 30rpx;
  border-radius: 999rpx;
}
```

- [ ] **Step 4: 写页面配置**

创建 `miniprogram/pages/chat/chat.json`：

```json
{
  "navigationBarTitleText": "NanZi 智能体",
  "usingComponents": {}
}
```

- [ ] **Step 5: 验证（真机）**

在开发者工具点「预览」，用手机扫码进入聊天页。

Expected：
- 先看到「正在进入…」，随后 web-view 铺满并加载出 EmbedChat；
- 若平台未配置域名，会看到业务域名报错——回到 Task 7 检查后台配置；
- 按手机返回键再进入，页面能重新签票并正常加载（ticket 是一次性的，每次进入都必须重新签）。

- [ ] **Step 6: 检查点（不提交）**

汇报：四个文件内容、真机截图或现象描述（是否成功进入 EmbedChat）。

---

### Task 4: 原生文件页 `pages/file/file`

**Files:**
- Create: `miniprogram/pages/file/file.js`
- Create: `miniprogram/pages/file/file.wxml`
- Create: `miniprogram/pages/file/file.wxss`
- Create: `miniprogram/pages/file/file.json`

**为什么需要它：** 小程序 `web-view` 内不能触发 `<a download>`（会被微信拦截），所以 EmbedChat 会把文件地址交给这个原生页处理。**`wx.downloadFile` 要求域名在「downloadFile 合法域名」白名单里**（见 Task 7）。

- [ ] **Step 1: 写页面逻辑**

创建 `miniprogram/pages/file/file.js`：

```js
const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp)$/i

Page({
  data: {
    status: 'downloading',
    message: '正在下载…',
  },

  onLoad(options) {
    const raw = (options && options.url) || ''
    let url = ''
    try {
      url = decodeURIComponent(raw)
    } catch (e) {
      url = raw
    }

    if (!url) {
      this.setData({ status: 'error', message: '缺少文件地址' })
      return
    }
    this.download(url)
  },

  download(url) {
    wx.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode !== 200) {
          this.setData({ status: 'error', message: '下载失败 (HTTP ' + res.statusCode + ')' })
          return
        }
        const filePath = res.tempFilePath || ''
        if (IMAGE_EXT.test(filePath) || IMAGE_EXT.test(url)) {
          this.saveImage(filePath)
          return
        }
        this.openDocument(filePath)
      },
      fail: () => {
        this.setData({ status: 'error', message: '下载失败，请检查网络或域名白名单' })
      },
    })
  },

  openDocument(filePath) {
    wx.openDocument({
      filePath,
      showMenu: true,
      success: () => this.setData({ status: 'done', message: '' }),
      fail: () => this.setData({ status: 'error', message: '暂不支持预览该格式' }),
    })
  },

  saveImage(filePath) {
    wx.saveImageToPhotosAlbum({
      filePath,
      success: () => this.setData({ status: 'done', message: '已保存到相册' }),
      fail: () => this.setData({ status: 'error', message: '保存失败（可能未授权相册权限）' }),
    })
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },
})
```

- [ ] **Step 2: 写页面结构**

创建 `miniprogram/pages/file/file.wxml`：

```xml
<view class="state">
  <text class="state-title">
    {{status === 'error' ? '处理失败' : (status === 'done' ? '已完成' : '请稍候…')}}
  </text>
  <text wx:if="{{message}}" class="state-desc">{{message}}</text>
  <button class="state-btn" bindtap="onBack">返回对话</button>
</view>
```

- [ ] **Step 3: 写样式**

创建 `miniprogram/pages/file/file.wxss`：

```css
.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  padding: 0 48rpx;
  box-sizing: border-box;
}

.state-title {
  font-size: 34rpx;
  color: #1f2937;
  margin-bottom: 16rpx;
}

.state-desc {
  font-size: 28rpx;
  color: #6b7280;
  text-align: center;
  line-height: 1.6;
}

.state-btn {
  margin-top: 40rpx;
  background-color: #2563eb;
  color: #ffffff;
  font-size: 30rpx;
  border-radius: 999rpx;
}
```

- [ ] **Step 4: 写页面配置**

创建 `miniprogram/pages/file/file.json`：

```json
{
  "navigationBarTitleText": "文件",
  "usingComponents": {}
}
```

- [ ] **Step 5: 验证（真机，需 Task 7 的域名配置已完成）**

在 EmbedChat 里触发一次文件下载（或先直接用开发者工具打开 `/pages/file/file?url=<编码后的文件地址>`）。

Expected：PDF/Word 能被 `wx.openDocument` 打开；图片提示已保存到相册。

- [ ] **Step 6: 检查点（不提交）**

汇报：四个文件内容、真机验证现象。

---

### Task 5: 欢迎页 `pages/index/index` 与页面清单

**Files:**
- Modify: `miniprogram/pages/index/index.js`
- Modify: `miniprogram/pages/index/index.wxml`
- Modify: `miniprogram/pages/index/index.wxss`
- Modify: `miniprogram/app.json`
- Delete: `miniprogram/pages/example/`（整个目录）

- [ ] **Step 1: 写欢迎页逻辑**

替换 `miniprogram/pages/index/index.js`（**去掉 Task 2 Step 6 加的临时测试按钮逻辑**）：

```js
Page({
  data: {
    entering: false,
  },

  onEnterChat() {
    this.setData({ entering: true })
    wx.navigateTo({
      url: '/pages/chat/chat',
      complete: () => this.setData({ entering: false }),
    })
  },

  onShareAppMessage() {
    return {
      title: 'NanZi 智能体',
      path: '/pages/index/index',
    }
  },
})
```

- [ ] **Step 2: 写欢迎页结构**

替换 `miniprogram/pages/index/index.wxml`：

```xml
<view class="page">
  <view class="brand">
    <text class="brand-title">NanZi 智能体</text>
    <text class="brand-sub">Natural language into executable outcomes</text>
  </view>

  <button class="enter-btn" loading="{{entering}}" bindtap="onEnterChat">
    开始对话
  </button>

  <text class="tip">首次进入将自动为你创建账号，无需注册</text>
</view>
```

- [ ] **Step 3: 写欢迎页样式**

替换 `miniprogram/pages/index/index.wxss`：

```css
.page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  padding: 0 64rpx;
  box-sizing: border-box;
  background-color: #f8fafc;
}

.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 96rpx;
}

.brand-title {
  font-size: 52rpx;
  font-weight: 600;
  color: #0f172a;
}

.brand-sub {
  margin-top: 16rpx;
  font-size: 26rpx;
  color: #64748b;
  text-align: center;
}

.enter-btn {
  width: 100%;
  background-color: #2563eb;
  color: #ffffff;
  font-size: 32rpx;
  border-radius: 999rpx;
}

.tip {
  margin-top: 32rpx;
  font-size: 24rpx;
  color: #94a3b8;
}
```

- [ ] **Step 4: 更新页面清单**

把 `miniprogram/app.json` 的 `pages` 改为（**保留文件里原有其它字段不动**）：

```json
  "pages": [
    "pages/index/index",
    "pages/chat/chat",
    "pages/file/file"
  ],
```

- [ ] **Step 5: 删除模板示例页**

删除整个 `miniprogram/pages/example/` 目录。

Run: `ls miniprogram/pages/`

Expected: 只剩 `index`、`chat`、`file` 三个目录。

- [ ] **Step 6: 验证**

Run: 在开发者工具点「编译」

Expected: 编译无报错；首页显示欢迎页；点「开始对话」能进入聊天页。

- [ ] **Step 7: 检查点（不提交）**

汇报：改动/删除的文件、编译结果、首页截图。

---

### Task 6: 端到端真机验收

- [ ] **Step 1: 走一遍完整链路**

真机预览 → 首页 → 开始对话 → 聊天页 → EmbedChat 加载 → 发一条消息 → 收到回复。

Expected: 全程无白屏；能正常对话。

- [ ] **Step 2: 验证会话隔离**

用**另一个微信号**（或让同事扫预览码）进入。

Expected: 两人看到各自的对话历史，**不串**。若串了，说明 `instance_id` 没逐用户派生（检查平台侧 `derive_instance_id`）。

- [ ] **Step 3: 验证附件与下载**

在 EmbedChat 里上传一个文件、并触发一次文件下载。

Expected: 上传走 `<input type="file">`；下载跳转到原生文件页并能预览。（**Android 与 iOS 行为可能不同，两端都要试。**）

- [ ] **Step 4: 验证 iOS 白屏规避**

iOS 真机进入聊天页。

Expected: web-view 正常加载（URL 已带 `#wechat_redirect`）。

- [ ] **Step 5: 验证无可用智能体的兜底**

让管理员**临时取消**「小程序用户」角色的可见智能体，再用新微信号进入。

Expected: 显示「尚未开放智能体，请联系管理员」，而不是空白页或报错。验证完请管理员勾回来。

- [ ] **Step 6: 验证切后台恢复**

聊天中切到微信后台，等 1 分钟再切回。

Expected: 会话仍在（若 web-view 被销毁重建，聊天页会自动重新签票）。

- [ ] **Step 7: 检查点（不提交）**

汇报：6 项验收的实际结果，特别标注任何 Android/iOS 差异。

---

### Task 7: 微信后台域名配置与上线前检查

**Files:** 无（全部是微信公众平台后台操作）

- [ ] **Step 1: 确认主体与备案**

微信公众平台 → 设置 → 基本设置，确认小程序为**企业/组织主体**；确认平台域名**已 ICP 备案**。

Expected: 个人主体无法继续（`web-view` 不被支持）。

- [ ] **Step 2: 配置业务域名**

微信公众平台 → 开发 → 开发管理 → 开发设置 → **业务域名** → 添加平台域名。

Expected: 需要上传校验文件到平台域名的根目录。新备案域名需**等待 24 小时**后才能配置。

- [ ] **Step 3: 配置 downloadFile 合法域名**

同一页面的 **downloadFile 合法域名** → 添加同一个平台域名。

Expected: 这是文件页 `wx.downloadFile` 能工作的前提；**不配会导致 Task 4 的下载失败**（报「不在以下 downloadFile 合法域名列表中」）。

- [ ] **Step 4: 确认不需要 request 合法域名**

云函数调用平台属于**云函数出网**，不受小程序 request 白名单约束。因此若没有别的需求，request 合法域名可以不配。

- [ ] **Step 5: 逐项核对上线清单**

对照 spec §13 逐项确认（平台侧与本工程侧合并）：

- [ ] 小程序为企业/组织主体
- [ ] 平台已部署在 https + 已 ICP 备案域名上
- [ ] 域名已配为**业务域名**（web-view）
- [ ] 域名已配为 **downloadFile 合法域名**（文件页）
- [ ] 云开发环境已创建，云函数已部署且环境变量已配（`NANZI_BASE_URL` / `NANZI_API_KEY`）
- [ ] 云网关账号已建，且**仅**授予「代他人签发嵌入凭证」一项 API 权限
- [ ] 平台侧 `miniprogram_enabled = true`
- [ ] 平台侧已给「小程序用户」角色**勾选可见智能体**
- [ ] 平台侧「小程序用户」角色**未勾选任何「外部 API」**
- [ ] 云网关 API Key 未出现在小程序代码、仓库或平台 `SystemConfig` 中
- [ ] Android + iOS 双端验收通过（附件上传、文件下载、白屏、切后台恢复）

- [ ] **Step 6: 检查点（不提交）**

汇报：后台配置项清单与核对结果（**不要写出任何 Key 的值**）。

---

## 已知缺口与本计划未覆盖项

1. **无法自动化测试**：本工程没有接入平台仓库的 pytest，验证靠开发者工具 + 真机。若后续要加自动化，可考虑小程序自动化 SDK（miniprogram-automator），本期未纳入。
2. **文件页对 Android/iOS 的差异**：`<input type="file">` 在 web-view 内的行为两端不一致，需要实机确定是否要降级为「原生页选文件后回传」。本期先用「下载走原生页」这一半。
3. **无 `chooseMessageFile`**：微信 JSSDK 不提供该能力（[官方支持的 JSSDK 接口](https://developers.weixin.qq.com/miniprogram/dev/component/web-view.html)里没有），所以「从聊天记录选文件」做不到，只能从相册/拍照/本地文件选。
4. **原生首页的作用**：它既是入口，也是降低「纯网页套壳」审核风险的手段。但**是否过审由微信判定，无法预先保证**——若被拒，备选是增加原生内容（如会话列表、消息通知）。
5. **`process.env` 在本地调试不可读**：腾讯云文档明确「环境变量无法在本地进行读取」([环境变量](https://docs.cloudbase.net/cloud-function/function-configuration/env))，因此云函数必须**上传到云端**才能验证配置，本地 F5 调试会拿到 undefined。
