# DooD HOST_DATA_DIR 文档补齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Docker/DooD 部署者在首次部署前明确配置 `HOST_DATA_DIR`，并能理解、验证平台容器与用户沙箱之间的工作区映射。

**Architecture:** 以宿主机真实数据目录为唯一挂载源，平台容器映射到 `/app/data`，宿主 Docker daemon 创建的用户沙箱映射到 `/workspace`。部署主指南负责首次配置，Docker README 负责操作细节，FAQ 负责故障诊断，公开运行时 FAQ 与根 FAQ 保持一致。

**Tech Stack:** Markdown、Docker Compose、Shell 验证命令。

---

### Task 1: 补充首次部署配置

**Files:**
- Modify: `HOW_TO_INSTALL.md`
- Modify: `docker/README.md`
- Modify: `docker/env.example`

- [ ] 在 Docker 部署首次配置步骤中将 `HOST_DATA_DIR` 标为 DooD 必配项。
- [ ] 添加 Linux 生产环境 Compose 示例和三层路径映射。
- [ ] 在环境模板中说明必须填写宿主机绝对路径，不能只依赖 `/app/data` 容器路径。

### Task 2: 补充 FAQ 与英文指南

**Files:**
- Modify: `FAQ.md`
- Modify: `data/docs/FAQ.md`
- Modify: `docker/README_EN.md`

- [ ] 修正旧的 `data/workspace/<user_id>` 表述为实际 `agent_workspaces/{user_key}` 结构。
- [ ] 添加未配置 `HOST_DATA_DIR` 导致沙箱 `/workspace/sessions` 为空的排查项。
- [ ] 在英文 Docker 指南中同步配置、映射和验证命令。

### Task 3: 静态一致性校验

- [ ] 搜索所有部署文档中的旧路径和 `HOST_DATA_DIR` 说明。
- [ ] 运行 `git diff --check`。
- [ ] 检查工作区状态，确认只包含本次文档范围及计划文件。
