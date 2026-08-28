# 技能工作台帮助安装指南恢复 Implementation Plan

> **For agentic workers:** 按当前会话约束在本地工作区逐项执行；不自动提交 Git，不启动服务或部署脚本。

**Goal:** 在现有技能工作台帮助弹窗中恢复第三方 Skills 安装详细说明，同时保持当前工作流、审批和技能管理功能不变。

**Architecture:** 只扩充 `SkillsManagement.vue` 的 `schema` Tab，将旧版 CLI、Git 和 Zip/Tar 说明整理为当前浅色帮助弹窗的分段内容。复用现有 `copyCommand`，不增加接口、路由或业务状态。

**Tech Stack:** Vue 3、TypeScript、Tailwind CSS、pytest 前端静态契约、vue-tsc。

---

### Task 1: 锁定安装指南和兼容性契约

**Files:**
- Modify: `tests/frontend/test_skill_flow_guide_contract.py`

- [x] **Step 1: Write the failing test**

新增测试断言 `SkillsManagement.vue` 同时保留当前主 Tab 和复制逻辑，并包含旧版安装说明的关键标题、命令、路径和安全规则。

- [x] **Step 2: Run test to verify it fails**

运行：

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_skill_flow_guide_contract.py -q
```

预期：新增安装指南契约因当前只有概览卡片而失败。

### Task 2: 恢复 schema Tab 的详细安装内容

**Files:**
- Modify: `frontend/src/views/SkillsManagement.vue:2156-2195`

- [x] **Step 1: Replace overview-only cards with detailed sections**

保留现有 `SKILL.md` 示例和 `copyCommand`，将安装概览扩展为：

- CLI 全局目录、本地与容器路径；
- 通用 `npx skills add <仓库地址> --skill <skill-id>` 形式和现有可复制示例；
- 个人技能 Git clone 目录；
- Zip/Tar 导入入口、`SKILL.md` 必需规则、覆盖模式；
- 第三方来源和脚本安全检查提示。

不修改 `activeHelpTab`、任何 API URL、导入函数、审批函数或市场链接样式。

- [x] **Step 2: Run focused tests**

运行：

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_skill_flow_guide_contract.py -q
```

预期：技能工作台相关契约全部通过。

### Task 3: Run frontend static verification

**Files:**
- Verify: `frontend/src/views/SkillsManagement.vue`
- Verify: `tests/frontend/test_skill_flow_guide_contract.py`

- [x] **Step 1: Run Vue type checking**

运行：`./node_modules/.bin/vue-tsc --noEmit`（工作目录：`frontend`）。

- [x] **Step 2: Run scoped diff checks**

运行：

```bash
git diff --check -- frontend/src/views/SkillsManagement.vue tests/frontend/test_skill_flow_guide_contract.py
```

- [x] **Step 3: Report manual verification boundary**

说明未启动 `./dev.sh`；用户可在控制台打开「？」并切换 `SKILL.md 规范与生态安装` Tab，检查滚动、复制按钮和现有 Tab 功能。
