# 技能工作台帮助弹窗安装指南恢复设计

## 目标

在技能工作台「？」帮助弹窗的 `SKILL.md 规范与生态安装` Tab 中恢复旧版第三方 Skills 安装详细说明，同时保留当前的全流程指引、审批发布、多版本隔离和现有技能操作功能。

## 背景与现状

旧版帮助弹窗包含以下详细内容：

- Skills 的用途说明；
- `npx skills add` 从第三方仓库安装平台全局技能；
- `git clone` 安装个人技能；
- Zip/Tar 导入要求；
- `SKILL.md` 必须存在的校验规则；
- 已存在技能时的覆盖模式与隔离说明。

当前版本将帮助弹窗改为 `flow`、`schema`、`audit` 三个主 Tab，`schema` 中只保留三种安装方式的概览卡片，导致旧版安装细节不可见。

## 方案

仅修改 `SkillsManagement.vue` 中 `activeHelpTab === 'schema'` 的展示内容，不回退整个帮助弹窗。

`schema` Tab 的内容顺序为：

1. `SKILL.md` YAML Frontmatter 示例；
2. 命令行安装：展示平台全局技能目录、通用 `npx skills add <仓库地址> --skill <skill-id>` 形式和当前可复制示例；
3. Git 安装：展示个人技能目录结构和 `git clone` 示例；
4. 压缩包导入：说明 Zip/Tar 导入入口、根目录或单层目录必须包含 `SKILL.md`，以及覆盖模式；
5. 保留当前 Skills 市场外链。

现有 `copyCommand` 方法和复制按钮继续复用，不新增 API、路由、状态字段或后端逻辑。

## 路径与文案约束

- 平台全局技能目录说明使用当前配置约定：本地默认 `~/.agents/skills`，容器环境默认 `/app/data/skills`；文案说明这是运行环境中由平台扫描的全局技能目录。
- 个人技能目录沿用实际 resolver 结构：本地 `data/agent_workspaces/{user_key}/skills`，容器对应 `/app/data/agent_workspaces/{user_key}/skills`。
- Git 示例使用占位符，不要求用户手工修改任何现有业务配置。
- 安装说明只描述文件落盘和发现规则，不承诺第三方仓库内容安全；增加“安装前确认来源、SKILL.md 和脚本内容”的提示。

## 兼容性边界

不修改以下内容：

- `activeHelpTab` 及现有三个主 Tab 的切换逻辑；
- `copyCommand` 和剪贴板反馈；
- 技能创建、编辑、上传、导入、删除、启停 API；
- 个人技能与平台技能的权限隔离；
- 发布申请、撤销、审核、版本归档和绑定智能体流程；
- 当前 `skills.sh` 市场链接。

## 验证方式

- 更新前端静态契约，确认安装说明和关键安全边界仍存在；
- 运行技能工作台相关前端契约测试；
- 运行 `vue-tsc --noEmit`；
- 运行限定范围的 `git diff --check`；
- 不启动服务、不执行部署脚本，由用户在控制台手动查看弹窗和复制命令交互。
