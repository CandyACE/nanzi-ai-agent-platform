# Implementation Plan: RAGFlow 元数据连接配置分组与连接测试

## Overview

在系统配置的元数据 RAGFlow 模式下，将服务地址与 API Key 组合为浅蓝色连接配置卡片，并增加基于当前表单值的 RAGFlow 数据集列表连通性测试。测试复用现有系统配置测试权限和 `RagFlowClient`，不自动保存配置、不新增数据库迁移。

## Tasks

### Task 1: 补充后端连接测试失败测试

Files:
- Create: `tests/api/portal/test_system_ragflow_connection.py`

Steps:
1. 为临时 URL/API Key、脱敏 Key 回退已保存 Key、缺失配置和 RAGFlow 异常分别编写异步测试。
2. Mock `RagFlowClient`、`ConfigService` 与权限依赖所需对象，断言只调用一次 `list_datasets(page=1, page_size=1)`。
3. 先运行该测试文件，确认在接口尚未实现时失败。

### Task 2: 实现后端 RAGFlow 元数据连接测试

Files:
- Modify: `app/api/portal/endpoints/system.py`

Steps:
1. 扩展测试请求模型，支持当前元数据 RAGFlow URL、API Key 和是否使用已保存 API Key。
2. 在 `test_connection` 增加 `ragflow_metadata` 分支，校验配置并构造 `RagFlowClient(config_prefix="ragflow", override_url=..., override_key=...)`。
3. 调用 `list_datasets(page=1, page_size=1)`，返回统一的状态、消息和数据集数量；处理配置缺失、HTTP 请求、超时和一般异常。
4. 确保 API Key 不进入日志、响应或错误消息。
5. 运行 Task 1 测试并确认通过。

### Task 3: 补充前端契约失败测试

Files:
- Create: `tests/frontend/test_system_config_ragflow_connection_contract.py`

Steps:
1. 为 RAGFlow 分组 class、测试状态 ref、测试函数、请求路径、加载态和结果文案增加源码契约断言。
2. 先运行该测试文件，确认当前 `SystemConfig.vue` 缺少目标实现时失败。

### Task 4: 实现 SystemConfig RAGFlow 分组与交互

Files:
- Modify: `frontend/src/views/SystemConfig.vue`

Steps:
1. 增加 RAGFlow 测试状态和按 key 查找当前配置值的辅助逻辑。
2. 将 `ragflow_api_url` 与 `ragflow_api_key` 从平铺循环中抽出为同一浅蓝底色、圆角、细边框分组，保留现有脱敏输入和显示/隐藏能力。
3. 在 API Key 下方增加“测试连接”按钮，使用当前未保存表单值；脱敏值改为让后端回退已保存密钥；成功不改变配置快照。
4. 增加测试中、成功、空数据集、失败和配置不完整状态，修改配置或切换 provider 后清除旧状态。
5. 保证桌面端与移动端不产生横向溢出，并保持现有蓝色视觉体系，不引入紫色高亮。
6. 运行 Task 3 测试和前端类型检查。

### Task 5: 聚焦回归与交付检查

Files:
- Modify: `tests/CHECKLIST.md`

Steps:
1. 运行后端连接测试、相关 RAGFlow 客户端测试和前端契约测试。
2. 运行 `vue-tsc --noEmit` 与 `git diff --check`。
3. 更新 `tests/CHECKLIST.md`，记录配置分组、一次数据集列表测试和未自动保存的行为。
4. 汇报未运行的真实 RAGFlow、浏览器和服务验收，不启动 `./dev.sh`。
