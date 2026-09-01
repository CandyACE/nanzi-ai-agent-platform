# 元数据同步实时日志 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为元数据手动同步增加当前任务的 SSE 实时日志抽屉，让用户看到同步阶段、进度、耗时和最终状态。

**Architecture:** POST 同步接口创建不可猜测的 task id 并登记 Redis 临时任务；后台同步服务通过一个独立的日志发布器写入带 TTL 的 Redis Stream。新增 SSE 接口先补读 Stream 再持续读取新事件，前端使用带鉴权请求头的 fetch 流解析 SSE，并在 `MetadataTables.vue` 右侧抽屉中展示当前任务日志。当前任务完成后保留前端日志，但 Redis 不保留历史任务。

**Tech Stack:** FastAPI `BackgroundTasks`、Redis asyncio client/Stream、SQLAlchemy 2.x、Vue 3 + TypeScript、现有 `createSseLineParser`、pytest。

---

### Task 1: 建立同步日志领域服务和事件模型

**Files:**
- Create: `app/services/metadata_sync_log_service.py`
- Test: `tests/services/test_metadata_sync_log_service.py`

- [ ] **Step 1: Write the failing tests**

  覆盖以下行为：

  ```python
  async def test_create_task_returns_unpredictable_id_and_initial_state():
      task = await service.create_task(dataset_id=17)
      assert task.task_id.startswith("sync_")
      assert task.dataset_id == 17
      assert task.status == "running"

  async def test_publish_and_read_events_preserve_order():
      task = await service.create_task(dataset_id=17)
      await service.publish(task.task_id, event="started", stage="queued", message="同步任务已开始", progress=0)
      await service.publish(task.task_id, event="progress", stage="metadata", message="正在读取元数据", progress=30)
      events = await service.read_events(task.task_id, after_id="0-0")
      assert [item["event"] for item in events] == ["started", "progress"]
      assert events[1]["progress"] == 30

  async def test_task_binding_rejects_wrong_dataset():
      task = await service.create_task(dataset_id=17)
      assert await service.belongs_to_dataset(task.task_id, 18) is False
  ```

  使用 fake Redis 对 `xadd`、`xrange`、`expire` 和任务状态读写做最小模拟，不连接真实 Redis。

- [ ] **Step 2: Run tests to verify they fail**

  Run: `PYTHONPATH=. pytest tests/services/test_metadata_sync_log_service.py -q`

  Expected: FAIL because the new service and event operations do not exist。

- [ ] **Step 3: Implement the minimal service**

  建立 `MetadataSyncLogService`，固定 key 前缀并实现：

  ```python
  TASK_KEY = "metadata_sync:task:{task_id}"
  STREAM_KEY = "metadata_sync:events:{task_id}"
  TASK_TTL_SECONDS = 1800

  async def create_task(dataset_id: int) -> SyncTask:
      task_id = f"sync_{secrets.token_urlsafe(18)}"
      await redis.hset(TASK_KEY.format(task_id=task_id), mapping={"dataset_id": dataset_id, "status": "running"})
      await redis.expire(TASK_KEY.format(task_id=task_id), TASK_TTL_SECONDS)
      return SyncTask(task_id=task_id, dataset_id=dataset_id, status="running")

  async def publish(task_id: str, *, event: str, stage: str, message: str,
                   progress: int | None = None, error_detail: str | None = None) -> dict:
      payload = build_event_payload(
          task_id=task_id,
          event=event,
          stage=stage,
          message=message,
          progress=progress,
          error_detail=error_detail,
      )
      await redis.xadd(STREAM_KEY.format(task_id=task_id), payload, maxlen=2000, approximate=True)
      await redis.expire(STREAM_KEY.format(task_id=task_id), TASK_TTL_SECONDS)
      await update_status_for_terminal_event(task_id, payload)
      return payload
  ```

  `build_event_payload` 统一补齐 `task_id`、`dataset_id`、`elapsed_ms`，终态只允许 `completed` 或 `failed`。

- [ ] **Step 4: Run tests to verify they pass**

  Run: `PYTHONPATH=. pytest tests/services/test_metadata_sync_log_service.py -q`

  Expected: all service tests PASS。

### Task 2: 把真实同步阶段接入日志发布器

**Files:**
- Modify: `app/services/metadata_rag_service.py:220-500`（`MetadataRagService.sync_dataset` 实际流程）
- Test: `tests/services/test_metadata_rag_sync.py`

- [ ] **Step 1: Write failing tests**

  对同步服务注入 fake log publisher 和 fake RAGFlow client，断言：

  ```python
  async def test_sync_dataset_publishes_real_stages_and_completed_event(fake_db, monkeypatch):
      await MetadataRagService.sync_dataset(db, 17, task_id="sync_test")
      assert [event.event for event in publisher.events] == [
          "started", "progress", "progress", "progress", "completed"
      ]
      assert publisher.events[-1].stage == "completed"

  async def test_sync_dataset_publishes_failed_event_and_updates_status(fake_db, monkeypatch):
      ragflow_client.create_dataset.side_effect = RuntimeError("RAGFlow unavailable")
      await MetadataRagService.sync_dataset(db, 17, task_id="sync_test")
      assert publisher.events[-1].event == "failed"
      assert publisher.events[-1].error_detail
  ```

- [ ] **Step 2: Run the focused tests and confirm the new signature/behavior fails**

  Run: `PYTHONPATH=. pytest tests/services/test_metadata_rag_sync.py -k 'sync_dataset and event' -q`

  Expected: FAIL because `sync_dataset` does not accept `task_id` or publish stage events。

- [ ] **Step 3: Add optional task logging without changing non-stream callers**

  将 `sync_dataset(db, dataset_id, task_id: str | None = None)` 保持向后兼容；当有 task id 时，在以下真实阶段发布事件：任务开始、读取数据集、检查/创建 RAGFlow 知识库、上传/更新文档、清理旧文档、完成。异常统一发布 `failed`，保留现有数据库失败状态和日志。

  不使用虚假固定百分比；每个阶段使用明确的阶段值，百分比只在能由实际表/文档数量计算时填写，否则为 `null`。

- [ ] **Step 4: Run service regression tests**

  Run: `PYTHONPATH=. pytest tests/services/test_metadata_rag_sync.py tests/ai/tools/test_document_paths.py -q`

  Expected: existing sync behavior and new event assertions PASS。

### Task 3: 改造同步接口并增加安全 SSE 端点

**Files:**
- Modify: `app/api/portal/endpoints/metadata.py:340-376`
- Create or modify: `tests/api/portal/test_metadata_sync_stream.py`

- [ ] **Step 1: Write failing endpoint tests**

  覆盖：POST 返回 task id 且只启动一次；SSE 首先收到已有 `started`，再收到后续事件；错误数据集或无同步权限返回 403/404；task 与 dataset 不匹配返回 404/400。

  ```python
  async def test_start_metadata_sync_returns_task_id(client, auth_headers, monkeypatch):
      response = await client.post("/api/portal/metadata/datasets/17/rag/sync")
      assert response.json()["data"]["task_id"].startswith("sync_")

  async def test_metadata_sync_events_replays_and_streams_events(client, task_id, auth_headers):
      response = await client.get(
          f"/api/portal/metadata/datasets/17/rag/sync/{task_id}/events",
          headers=auth_headers,
      )
      assert "event: started" in response.text
      assert "event: progress" in response.text
  ```

- [ ] **Step 2: Run endpoint tests to verify they fail**

  Run: `PYTHONPATH=. pytest tests/api/portal/test_metadata_sync_stream.py -q`

  Expected: FAIL because POST does not return task id and the SSE route is absent。

- [ ] **Step 3: Implement task creation and SSE streaming**

  POST 在加入 `BackgroundTasks` 前创建 task 并发布 `started`，将 `task_id` 传给 `MetadataRagService.sync_dataset`；保留现有权限、启用状态和重复同步检查。

  SSE 端点使用 `StreamingResponse(media_type="text/event-stream")`，先用 `XRANGE` 读取已有事件，再用 `XREAD BLOCK` 读取新事件；每条输出为：

  ```text
  id: 1710000000000-0
  event: progress
  data: {"task_id":"sync_xxx","dataset_id":17,"stage":"metadata","message":"正在读取元数据","progress":30,"elapsed_ms":420}

  ```

  收到 `completed`/`failed` 后发送终态并结束响应；客户端断开时取消读取协程，不取消后台同步。验证 task 绑定和权限后才允许订阅。

- [ ] **Step 4: Run endpoint tests to verify they pass**

  Run: `PYTHONPATH=. pytest tests/api/portal/test_metadata_sync_stream.py -q`

  Expected: all endpoint tests PASS。

### Task 4: 实现前端同步日志状态与右侧抽屉

**Files:**
- Modify: `frontend/src/api/metadata.ts:124-136`
- Modify: `frontend/src/views/MetadataTables.vue:406-448` and the dataset detail template near the sync action
- Test: `tests/frontend/test_metadata_sync_log_contract.py`

- [ ] **Step 1: Write failing frontend contract tests**

  断言前端使用返回的 `task_id`，通过 fetch 流而不是原生 `EventSource` 建立带鉴权的 SSE，处理四类事件、断线提示、完成后保留抽屉，以及手动关闭不取消任务。

  ```python
  def test_metadata_tables_uses_task_id_and_authenticated_sse_fetch():
      source = METADATA_TABLES.read_text(encoding="utf-8")
      assert "task_id" in source
      assert "text/event-stream" in source
      assert "getReader()" in source
      assert "同步日志连接已断开" in source
      assert "同步成功" in source
      assert "同步失败" in source
  ```

- [ ] **Step 2: Run the contract test and verify it fails**

  Run: `pytest --confcutdir=tests/frontend tests/frontend/test_metadata_sync_log_contract.py -q`

  Expected: FAIL because the current page only waits 3.5 seconds and has no log drawer。

- [ ] **Step 3: Implement the minimal frontend flow**

  在 metadata API 中定义：

  ```ts
  syncToRag: (id: number) => axios.post<{ data: { task_id: string } }>(`${API_BASE}/datasets/${id}/rag/sync`)
  ```

  在 `MetadataTables.vue` 增加当前任务状态、日志数组、AbortController 和抽屉开关；POST 成功后使用 `fetch` 携带现有认证头读取 SSE，复用 `createSseLineParser` 解析 `event/data`。事件按顺序追加，`completed`/`failed` 停止读取但不关闭抽屉；断线只设置连接提示并保留已收日志。移除固定 3.5 秒作为主要状态来源，仅在终态后刷新数据集详情。

  抽屉固定在详情页右侧，展示数据集名称、状态、耗时、当前阶段、进度条和可滚动日志列表；关闭按钮只清理前端展示状态，不发送取消请求。

- [ ] **Step 4: Run frontend contract tests**

  Run: `pytest --confcutdir=tests/frontend tests/frontend/test_metadata_sync_log_contract.py -q`

  Expected: PASS。

### Task 5: 集成回归与文档自检

**Files:**
- Modify: `tests/CHECKLIST.md`，记录新增元数据同步实时日志测试覆盖
- Review: `docs/superpowers/specs/2026-09-01-metadata-sync-live-log-design.md`

- [ ] **Step 1: Run the complete focused regression set**

  Run:

  ```bash
    PYTHONPATH=. pytest tests/services/test_metadata_sync_log_service.py tests/services/test_metadata_rag_sync.py tests/api/portal/test_metadata_sync_stream.py tests/frontend/test_metadata_sync_log_contract.py -q
  ```

  Expected: all focused tests PASS。

- [ ] **Step 2: Run formatting/diff checks**

  Run: `git diff --check`

  Expected: no output and exit code 0。

- [ ] **Step 3: Update the checklist**

  在 `tests/CHECKLIST.md` 增加“元数据同步 SSE 实时日志”条目，明确代码测试已覆盖，但真实 Redis、浏览器 SSE、RAGFlow 联调未在 Agent 侧执行。

- [ ] **Step 4: Review implementation boundary**

  确认没有修改通用任务历史、没有引入数据库迁移、没有取消后台任务语义、没有启动 `./dev.sh`、Docker 或生产数据库操作；确认用户工作区未混入无关改动。

- [ ] **Step 5: Commit the implementation**

  ```bash
  git add app/services/metadata_sync_log_service.py app/services/metadata_rag_service.py app/api/portal/endpoints/metadata.py frontend/src/api/metadata.ts frontend/src/views/MetadataTables.vue tests/services/test_metadata_sync_log_service.py tests/services/test_metadata_rag_sync.py tests/api/portal/test_metadata_sync_stream.py tests/frontend/test_metadata_sync_log_contract.py tests/CHECKLIST.md
  git commit -m "feat: 增加元数据同步实时日志"
  ```
