# NanZi 登录页品牌主视觉轮播 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将登录页左侧主视觉改造成 B 默认、首屏轻随机、B/A/C 固定循环的品牌章节轮播，并让品牌名称与英文副标题按品牌个性化配置统一显示。

**Architecture:** 保留 `Login.vue` 右侧认证表单和认证流程，只重构左侧视觉状态。三个章节由静态数据驱动；一个定时器和暂停原因集合管理轮播；统一 computed 文案负责默认品牌和个性化品牌。主视觉使用动态 `iconUrl`，不使用写死产品名的 wordmark SVG。

**Tech Stack:** Vue 3 `<script setup>`、TypeScript、Tailwind CSS、`useBranding`、pytest 静态契约测试、Vite 构建。

---

### Task 1: 建立失败优先的登录页轮播契约测试

**Files:**
- Create: `tests/frontend/test_login_visual_carousel_contract.py`
- Reference: `frontend/src/views/Login.vue`

- [ ] **Step 1: 写失败测试**

测试读取 `Login.vue` 源码并锁定：章节 key 为 `b`、`a`、`c`；默认文案包含 `NanZi · 智能体平台` 和 `Your Intelligent Agent Platform`；文案解析读取 `branding.value.enabled`、`product_name`、`login_subtitle`；首屏使用 `sessionStorage` 与 `Math.random()`；间隔为 `7000`；存在 `clearInterval`、`prefers-reduced-motion`、暂停/恢复函数；指示器包含 `aria-label` 和 `aria-current`；视觉使用 `:src="iconUrl"`，不引用静态 wordmark SVG。

测试应采用现有静态契约模式：

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def login_source():
    return (ROOT / "frontend/src/views/Login.vue").read_text(encoding="utf-8")


def test_login_visual_carousel_contracts():
    source = login_source()
    for text in ("key: 'b'", "key: 'a'", "key: 'c'", "NanZi · 智能体平台", "Your Intelligent Agent Platform"):
        assert text in source
    for text in ("branding.value.enabled", "branding.value.product_name", "branding.value.login_subtitle", "sessionStorage", "Math.random()", "7000", "clearInterval", "prefers-reduced-motion", "pauseSlideTimer", "resumeSlideTimer", "aria-current", ':src="iconUrl"'):
        assert text in source
    assert "nanzi-wordmark-on-light.svg" not in source
    assert "nanzi-wordmark-on-dark.svg" not in source
```

- [ ] **Step 2: 运行测试确认失败**

运行：`pytest --confcutdir=tests/frontend -q tests/frontend/test_login_visual_carousel_contract.py`

预期：FAIL，因为当前登录页仍是旧的五个 slide，没有 B/A/C key、首屏随机、暂停控制和 reduced-motion 支持。

### Task 2: 实现统一品牌文案、三章节数据和轮播状态

**Files:**
- Modify: `frontend/src/views/Login.vue:1-150`

- [ ] **Step 1: 增加登录页默认文案**

定义 `DEFAULT_LOGIN_BRAND_NAME = 'NanZi · 智能体平台'` 与 `DEFAULT_LOGIN_SUBTITLE = 'Your Intelligent Agent Platform'`。将 `productName` 和 `loginSubtitle` 改为：仅当 `branding.value.enabled` 为真且对应配置非空时使用配置，否则使用这两个默认值。左侧三屏和移动头部必须共用这两个 computed 值。

- [ ] **Step 2: 用 B/A/C 替换旧 slides**

按 `b → a → c` 声明三个章节，分别使用以下主标题和能力标签：

```ts
const slides = [
  { key: 'b', title: '从自然语言到可执行结果', features: ['ChatBI', 'Knowledge', 'MCP'] },
  { key: 'a', title: '让智能体成为组织的第二操作系统', features: ['开放', '智能', '可控'] },
  { key: 'c', title: '一个入口，连接所有智能能力', features: ['Agents', 'Tools', 'Knowledge'] },
]
```

每项同时保留当前主题所需的描述、渐变、强调色和光晕字段；章节数据不得重复放产品名或统一品牌副标题。

- [ ] **Step 3: 实现首屏轻随机与固定循环**

首次进入时从 `sessionStorage` 读取首屏索引；没有值时使用加权随机生成并保存：B 章节概率 50%，A/C 各 25%。下一屏始终使用 `(currentSlide + 1) % slides.length`。自动播放固定为 `7000` 毫秒，`restartSlideTimer()` 必须先 `clearInterval` 再创建 interval，避免重复定时器。

- [ ] **Step 4: 实现暂停与 reduced-motion**

使用 `reactive(new Set<'visual-hover' | 'form-focus'>())` 保存暂停原因。左侧悬停添加/删除 `visual-hover`，右侧表单聚焦添加/删除 `form-focus`；仅在没有暂停原因时恢复定时器。挂载时读取 `window.matchMedia('(prefers-reduced-motion: reduce)')`，匹配时不自动播放；卸载时清理 interval 和 media-query listener。

- [ ] **Step 5: 重新运行定向测试**

运行同一 pytest 命令。若仍因模板事件或指示器未加入而失败，保留失败结果并继续 Task 3，不修改测试迎合旧实现。

### Task 3: 接入视觉模板、品牌锁定和可访问交互

**Files:**
- Modify: `frontend/src/views/Login.vue:150-390`

- [ ] **Step 1: 将品牌锚点固定在左上角**

在左侧主视觉面板的 `absolute top-10 left-10 xl:top-12 xl:left-12` 区域使用 `:src="iconUrl"`、`{{ productName }}` 和 `{{ loginSubtitle }}`。B 章节只改变颜色，不改变内容层级。不要把品牌锁定区放进章节居中的内容容器，也不要引用 `nanzi-wordmark-on-light.svg` 或 `nanzi-wordmark-on-dark.svg`，避免个性化产品名称被静态文字覆盖。

- [ ] **Step 2: 渲染章节内容**

主标题使用 `slide.title`，描述使用章节 `desc`，标签使用 `slide.features`；章节英文辅助描述不替代品牌名下方的统一英文副标题。装饰网格、光晕、连线设置 `aria-hidden="true"`。

- [ ] **Step 3: 加入暂停事件和可访问指示器**

左侧绑定 `@mouseenter="pauseSlideTimer"` / `@mouseleave="resumeSlideTimer"`，右侧登录面板绑定同名事件但传入不同暂停原因。指示器使用真实按钮，并包含：

```vue
:aria-label="`切换到${slide.title}主视觉`"
:aria-current="currentSlide === index ? 'true' : undefined"
@click="selectSlide(index)"
```

`selectSlide(index)` 只更新章节并重新计时，不修改表单输入或路由。

- [ ] **Step 4: 完成响应式和减少动画样式**

桌面端保留完整轮播；`lg` 以下隐藏复杂背景和自动轮播，仅保留移动头部的动态图标、统一品牌名称和英文副标题。加入 `motion-reduce:transition-none`，reduced-motion 下仍可手动切换。

- [ ] **Step 5: 运行契约测试确认变绿**

运行：`pytest --confcutdir=tests/frontend -q tests/frontend/test_login_visual_carousel_contract.py`

预期：PASS。

### Task 4: 构建验证和浏览器验收

**Files:**
- Verify: `frontend/src/views/Login.vue`
- Verify: `tests/frontend/test_login_visual_carousel_contract.py`
- Verify: `docs/superpowers/specs/2026-08-03-login-visual-carousel-design.md`

- [ ] **Step 1: 运行相关契约测试**

```bash
pytest --confcutdir=tests/frontend -q tests/frontend/test_login_visual_carousel_contract.py tests/frontend/test_nanzi_brand_assets_contract.py
```

预期：相关测试全部 PASS；其他宽泛测试的既有失败单独记录。

- [ ] **Step 2: 运行 Vite 构建**

```bash
cd frontend
NODE_OPTIONS=--max-old-space-size=4096 node ./node_modules/vite/bin/vite.js build
```

预期：构建成功；Browserslist、chunk size 等既有 warning 单独记录。

- [ ] **Step 3: 用户手动启动后做浏览器验收**

检查默认/随机首屏、7 秒固定顺序、悬停/聚焦暂停、指示器手动切换且输入不丢失；分别验证品牌个性化关闭时三屏显示 `NanZi · 智能体平台`，开启并填写产品名称/登录副标题后三屏统一显示配置值；验证宽屏、窄屏、移动端和 reduced-motion 无水平滚动、破图或表单跳动。

- [ ] **Step 4: 检查工作区变更**

运行 `git diff --check` 和 `git status --short`，只确认本计划涉及的登录页、测试和设计/计划文档；不自动暂存或提交，最终提交由用户控制。
