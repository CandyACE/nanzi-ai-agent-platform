# Dashboard 主题导航设计

## 背景

当前 Dashboard 使用深色左侧导航，工作台内容区域是浅色。用户认可亮色导航方案，希望保留现有菜单结构，同时提供亮色/暗色切换入口。

## 目标

- 左侧导航支持亮色视觉，接近已确认的预览：白色背景、浅蓝选中态、深灰文字。
- 保留现有深色导航作为暗色主题。
- 主题切换放在左侧导航底部的个人区附近，展开时显示“亮色/暗色”，收起时仍可通过图标和提示操作。
- 主题选择保存到浏览器本地，刷新和重新进入 Dashboard 后保持。
- 主题状态只作用于 Dashboard 侧栏，不给 `html` 添加全局 `dark` class，避免右侧业务内容跟随变化；不引入后端接口或数据库字段。

## 非目标

- 不调整菜单权限、菜单分组、路由地址或移动端侧栏行为。
- 不把工作台业务卡片整体重做成暗色；本次只负责平台壳层和已有暗色变体的主题入口。
- 不新增个人中心设置页或服务端用户偏好同步。

## 方案

新增一个轻量的 `useAppTheme` 单例 composable，维护 `light/dark` 状态，读写 `localStorage`，并记录 `document.documentElement.dataset.theme`。Dashboard 只通过该状态为侧栏、菜单项和用户区选择对应 Tailwind 类，顶部栏和主内容背景保持现状。

亮色主题的导航信息架构仍使用现有 `filteredMenuGroups`，只更换外观；主题切换控件放在用户资料按钮上方，避免与退出、通知等顶部操作混在一起。折叠导航时保留太阳/月亮图标及 `title`，移动端沿用同一控件。

## 验证

- 前端契约测试检查主题 composable、持久化 key、`html.dark`、亮暗导航类和可访问切换入口。
- `pytest --confcutdir=tests/frontend tests/frontend/test_dashboard_theme_contract.py -q`
- `vue-tsc --noEmit`
- `git diff --check`
