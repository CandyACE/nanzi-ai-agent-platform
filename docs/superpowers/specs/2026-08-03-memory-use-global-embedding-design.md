# 记忆工作台改用系统全局 Embedding 配置

**日期：** 2026-08-03  
**状态：** 已批准，实施中

## 概要

系统配置已提供全局 Embedding（`embed_api_url` / `embed_api_key` / `embed_model_name` / `embed_dimensions`），记忆工作台另有一套 `memory_embedding_*`，造成重复配置。统一为记忆向量读写只使用系统全局 Embedding。

## 决策

| 项 | 选择 |
|---|---|
| UI | 记忆工作台删除 Embedding 配置组（方案 A） |
| DB | 保留 `memory_embedding_*` 行，代码不再读取（方案 B） |
| 实现 | 记忆路径统一走全局配置（方案 1） |

## 行为

- **唯一配置源**：系统配置 `embed_*`
- **降级**：URL/Key 为空 → `llm_base_url` / `llm_api_key`；不再回退 `memory_embedding_*`
- **记忆页「测试 Embedding」**：保留按钮，实际测试全局 Embedding
- **运维**：若旧记忆向量模型/维度与全局不一致，需在记忆工作台重建索引

## 改动范围

- `app/services/ai/embedding_client.py`：统一解析全局配置
- `app/api/portal/endpoints/system.py`：全局连通性测试去掉 memory 降级
- `frontend/src/views/MemoryManagement.vue`：删除 Embedding 配置组
- `tests/services/test_global_embedding_config.py`：更新断言与用例
- `tests/CHECKLIST.md`：同步说明

## 非目标

- 不删除 DB 中 `memory_embedding_*` seed / 历史行
- 不改系统配置页全局 Embedding UI 的手工编辑能力

## 后续补充（2026-08-03）

系统配置 Embedding 区支持「从模型管理加载」：选择已启用的 Embedding 模型后，一键填入 `embed_api_url` 与 `embed_model_name`。API Key 因列表接口脱敏无法自动填入（模型管理已有 Key 时可留空，由运行时 registry 解析）；`embed_dimensions` 仍需人工核对。
