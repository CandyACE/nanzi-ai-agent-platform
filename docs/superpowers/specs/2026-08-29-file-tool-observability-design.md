# 文件工具思考卡片元信息设计

## 目标

让思考卡片在执行 `Read`、`Write`、`Edit`、`Glob`、`Grep` 等文件操作时，直接显示操作类型和逻辑工作区路径，避免用户只能看到“工具完成”而不知道操作了哪个文件。

## 方案

在现有工具完成日志中增加结构化的文件操作元信息，同时保持现有工具输出、状态判断和审计轨迹不变。前端优先使用结构化字段渲染；缺少字段时继续兼容现有 `details` 文本。

统一字段如下：

```json
{
  "operation": "read",
  "path": "/workspace/docs/report.md",
  "target_type": "file",
  "file_name": "report.md",
  "file_extension": ".md",
  "size_bytes": 12698,
  "line_count": 238,
  "range": {"start": 20, "end": 80},
  "pattern": null,
  "match_count": null,
  "changed": null
}
```

字段按工具按需返回：

- `Read`：`operation`、`path`、文件名/扩展名、可计算时的大小和行数、读取范围。
- `Write` / `Edit`：`operation`、`path`、文件名/扩展名、写入后大小和行数、`changed`；编辑工具可补充增删行统计。
- `Glob`：`operation`、搜索根路径、`pattern`、匹配数量。
- `Grep`：`operation`、搜索根路径、搜索模式、匹配数量。
- `Bash`：本阶段不解析命令中的路径，继续使用命令摘要、状态和耗时。

## 路径与安全边界

- Docker、SSH、本地执行统一对外显示逻辑路径，例如 `/workspace/sessions/<id>/file.txt`。
- 不向前端、模型或普通工具日志暴露 `/app/data/...` 等宿主机真实路径。
- 不记录 inode、宿主机权限细节和完整内容 hash；如后续审计需要，单独设计审计字段。
- 文件级元数据计算失败不能导致原工具调用失败，字段允许为空。

## 前端展示

思考卡片标题显示“操作类型 + 逻辑路径”，详情显示摘要元数据。例如：

```text
读取文件：/workspace/docs/report.md
238 行 · 12.4 KB · 成功 · 18ms
```

```text
搜索文件：/workspace
关键词：HOST_DATA_DIR · 命中 5 处 · 22ms
```

原有错误状态、耗时、折叠行为和完整工具输出不改变。

## 测试

- 后端单测覆盖各文件工具的元信息构造、逻辑路径输出和元数据计算失败降级。
- 前端契约测试覆盖结构化字段存在时的标题/详情展示，以及旧日志无字段时的兼容展示。
- 运行现有前端契约测试和 `vue-tsc --noEmit`。
