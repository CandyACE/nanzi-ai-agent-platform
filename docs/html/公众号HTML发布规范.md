# 公众号 HTML 文章发布规范

> 适用于 NanZi 实战连载系列。每次发布新文章前，按以下清单逐项检查并修复。

---

## 一、内容准确性检查

### 1.1 与实际代码对比核查

在发布前，对照项目实际代码，检查以下描述是否与实现一致：

| 检查点 | 验证方法 |
|---|---|
| 代码路径、文件名 | `grep -r "关键词" app/` 确认文件是否存在 |
| 配置字段名称与默认值 | 搜索 `ConfigService.get("字段名"` 核对默认值 |
| API 路径 | 搜索 `@router.` 确认 endpoint 路径 |
| 权限字段名 | 搜索 `element:` 确认权限字符串 |
| 函数/类名称 | 搜索 `def 函数名` 或 `class 类名` 确认存在 |
| 状态枚举值 | 搜索 status 相关常量确认拼写 |

### 1.2 常见易错描述

| 错误类型 | 示例 | 修正方式 |
|---|---|---|
| 数值用「约」字模糊化 | `约 64KB` | 改为精确值 `64 KB`（65536 字节） |
| 范围限制无代码依据 | `钳制 1–3` | 改为「调用方可配置」或给出代码出处 |
| 前端组件名不存在 | `SkillCreatedBanner` | 改为描述实现行为：「前端解析标记后弹出横幅」 |
| 缺漏关键服务文件 | 代码速查没有统计服务 | 补充所有相关核心文件路径 |

---

## 二、小白友好性检查

### 2.1 专业名词是否有注解

遇到以下类型词汇，必须在首次出现时加括号注解：

| 术语 | 推荐注解写法 |
|---|---|
| YAML frontmatter | `YAML frontmatter（即文件顶部用 --- 包裹的键值对配置）` |
| RBAC | `RBAC（基于角色的权限控制）` |
| ReAct 循环 | `ReAct 循环（模型思考→工具调用→观察的推理执行模式）` |
| slug | `slug（URL 友好的短名称别名）` |
| LRU 缓存 | `LRU 缓存（最近最少使用的自动淘汰缓存）` |
| TTL | `TTL（缓存有效期，超时自动失效）` |
| Docker 卷映射 | 加跳过提示：「不使用 Docker 部署的可跳过本节」 |

### 2.2 关键流程是否有完整步骤

凡涉及多步操作（如审核→生效），必须给出完整步骤卡片，不能只说结论：

```html
<!-- 绿色步骤卡片模板 -->
<section style="margin:0 0 16px 0;padding:12px 14px;background:#f0fdf4;border:1px solid #a7f3d0;border-radius:10px;">
  <p style="margin:0 0 6px 0;font-size:13px;font-weight:bold;color:#065f46;">✅ [操作名称] 完整步骤</p>
  <p style="margin:0;font-size:13px;color:#374151;line-height:1.9;">
    1. 第一步<br/>
    2. 第二步<br/>
    3. 第三步<br/>
    <span style="color:#6b7280;font-size:12px;">⚠️ 跳过第 X 步会导致……</span>
  </p>
</section>
```

### 2.3 可跳过章节提示模板

针对有门槛的章节（如 Docker、CLI、Git），在章节开头加黄色提示条：

```html
<p style="margin:0 0 6px 0;font-size:13px;color:#9a3412;line-height:1.75;background:#fffbeb;padding:6px 10px;border-radius:6px;border-left:3px solid #f59e0b;">
  💡 <strong>如果你不熟悉 [技术名称]，可以跳过本节</strong>，直接使用 [替代方案] 完成即可。
</p>
```

---

## 三、移动端兼容检查

> 公众号几乎全是手机阅读，以下项目每篇必查。

### 3.1 最外层 section 样式

必须包含以下属性，防止内容溢出和断词异常：

```html
<section style="
  box-sizing:border-box;
  font-size:16px;
  color:#3f3f3f;
  line-height:1.8;
  letter-spacing:0.5px;
  text-align:justify;
  font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue','PingFang SC','Hiragino Sans GB','Microsoft YaHei',Arial,sans-serif;
  max-width:760px;
  margin:0 auto;
  padding:0 2px;
  word-break:break-word;
  overflow-wrap:break-word;
">
```

### 3.2 表格必须加横向滚动包裹

多列表格（≥3列）在手机上必须能左右滑动，否则会被截断：

```html
<!-- ✅ 正确写法：包裹 overflow-x:auto -->
<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">
  <table style="width:100%;border-collapse:collapse;font-size:12px;line-height:1.65;">
    …
  </table>
</div>

<!-- ❌ 错误写法：裸 table，手机会截断 -->
<table style="width:100%;border-collapse:collapse;">…</table>
```

**批量修复脚本**（Python，在项目根目录执行）：

```python
import re

with open("docs/html/文章.html", "r", encoding="utf-8") as f:
    html = f.read()

html = re.sub(
    r'(<table style="width:100%;border-collapse:collapse;font-size:12px;line-height:1\.65;")',
    r'<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">\1',
    html
)
html = re.sub(r'(</table>)', r'\1</div>', html)

with open("docs/html/文章.html", "w", encoding="utf-8") as f:
    f.write(html)

print("表格包裹数量：", html.count('<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">'))
```

### 3.3 长代码/路径字符串必须断词

含有长路径或命令的 `<p>` 和代码块必须加 `word-break:break-all`：

```html
<!-- 终端命令行 -->
<p style="…;overflow-x:auto;word-break:break-all;">
  git clone [仓库地址] ./data/agent_workspaces/[user_key]/skills/[skill_id]
</p>

<!-- 代码速查段（含多条 app/ 路径） -->
<p style="…;word-break:break-all;">
  • 解析与扫描：<code>app/services/ai/skill_resolver.py</code><br/>
  …
</p>
```

### 3.4 pre 代码块

`<pre>` 标签必须有 `overflow-x:auto`，防止代码过长撑破布局：

```html
<pre style="…;overflow-x:auto;white-space:pre;">
  代码内容
</pre>
```

### 3.5 图片占位符背景色

图片占位区域背景必须与贴入截图的背景色一致，避免色差。
截图背景为白色时：

```html
<!-- ✅ 白色背景，无色差 -->
<section style="…;border:1px dashed #94a3b8;background:#ffffff;…">
```

**批量替换为白色背景（Shell）**：

```bash
sed -i '' \
  's/border:1px dashed #94a3b8;background:#f8fafc/border:1px dashed #94a3b8;background:#ffffff/g' \
  docs/html/文章.html
```

---

## 四、视觉规范

### 4.1 Header Banner 配色

推荐两套科技风配色，二选一：

**深蓝科技风（推荐）**

```html
<section style="
  background:linear-gradient(135deg,#060c1f 0%,#0a1628 48%,#0d2040 100%);
  box-shadow:0 4px 24px rgba(56,189,248,0.15);
">
  <!-- 期号文字 color:#7dd3fc  -->
  <!-- 主标题   color:#f8fafc  -->
  <!-- 副标题   color:#bae6fd  -->
</section>
```

**深绿科技风（备选）**

```html
<section style="
  background:linear-gradient(135deg,#064e3b 0%,#022c22 48%,#111827 100%);
  box-shadow:0 4px 20px rgba(16,185,129,0.15);
">
  <!-- 期号文字 color:#6ee7b7  -->
  <!-- 主标题   color:#f8fafc  -->
  <!-- 副标题   color:#a7f3d0  -->
</section>
```

### 4.2 章节标题色带规范

每个大章节用不同颜色左边框区分，保持全系列风格统一：

| 章节类型 | 左边框颜色 | 适用场景 |
|---|---|---|
| 背景/导言 | `#10b981`（绿） | 来龙去脉、为什么需要 |
| 架构/原理 | `#0891b2`（青） | 技术架构、设计思路 |
| 创建/操作 | `#7c3aed`（紫） | 如何创建、操作步骤 |
| 管理/运维 | `#d97706`（橙） | 管理、审核、统计 |
| 使用/触发 | `#10b981`（绿） | 如何使用、触发方式 |
| 工具/命令 | `#0891b2`（青） | 工具指令、API 速查 |
| FAQ/补充  | `#ef4444`（红） | 常见问题、注意事项 |

### 4.3 卡片色系速查

| 场景 | 背景色 | 边框色 | 标题色 |
|---|---|---|---|
| 成功/正向提示 | `#f0fdf4` | `#a7f3d0` | `#065f46` |
| 信息/说明 | `#ecfeff` | `#a5f3fc` | `#0e7490` |
| 警告/注意 | `#fffbeb` | `#fde68a` | `#b45309` |
| 危险/重要 | `#fef2f2` | `#fecaca` | `#991b1b` |
| 功能/扩展 | `#f5f3ff` | `#ddd6fe` | `#5b21b6` |
| 代码/中性 | `#f8fafc` | `#e2e8f0` | `#334155` |

---

## 五、发布前最终检查清单

```
内容准确性
□ 对照代码核查了所有技术描述（路径/字段名/状态值/阈值/默认值）
□ 前端组件名已在项目中确认存在
□ 代码速查段包含所有核心文件（服务、API、工具、统计等）

小白友好性
□ 专业术语首次出现时已加括号注解
□ 有技术门槛的章节（Docker/CLI）已加「可跳过」黄色提示
□ 多步操作流程已给出完整步骤卡片（含跳步警告）

移动端兼容
□ 最外层 section 已加 word-break / overflow-wrap / max-width
□ 所有 ≥3 列表格已包 overflow-x:auto div
□ 长代码路径行已加 word-break:break-all
□ pre 代码块已有 overflow-x:auto
□ 图片占位符背景色与截图背景一致（白色截图 → #ffffff）

视觉规范
□ Header Banner 配色已选定（深蓝或深绿）
□ 章节色带与系列风格一致
□ 卡片颜色语义正确（红=危险，绿=成功，橙=警告）
```

---

*最后更新：2026-08-28 · 基于 A08-skills.html 修订经验整理*

---

## 六、微信编辑器兼容：代码块格式丢失

### 问题

`<pre>` 标签粘贴进微信编辑器后换行和缩进全部消失，代码挤成一坨。

### 原因

微信编辑器不保留 `white-space:pre` 的换行语义，`\n` 被吞掉。

### 修复方法

**把 `<pre>` 转为 `<p>`，换行用 `<br/>`，空格用 `&nbsp;`。**

Python 批量修复脚本：

```python
import re

with open("docs/html/文章.html", "r", encoding="utf-8") as f:
    html = f.read()

def convert_pre(m):
    style = m.group(1)
    content = m.group(2)
    lines = content.split('\n')
    converted = []
    for line in lines:
        stripped = line.lstrip(' ')
        leading = len(line) - len(stripped)
        converted.append('&nbsp;' * leading + stripped)
    inner = '<br/>\n'.join(converted)
    new_style = style.replace('white-space:pre;', '').replace('white-space:pre', '')
    new_style = new_style.rstrip(';') + ';white-space:normal;'
    return f'<p style="{new_style}">{inner}</p>'

new_html = re.sub(
    r'<pre style="([^"]+)">(.+?)</pre>',
    convert_pre,
    html,
    flags=re.DOTALL
)

with open("docs/html/文章.html", "w", encoding="utf-8") as f:
    f.write(new_html)
```

> 发布前必须执行，否则树形目录、伪代码块在微信里全部变成一行。
