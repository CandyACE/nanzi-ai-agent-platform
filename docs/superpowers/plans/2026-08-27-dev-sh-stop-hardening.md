# dev.sh 生命周期命令健壮性加固 Implementation Plan

> **For agentic workers:** 按本计划逐项执行；实现过程中不启动真实服务，不自动提交。

## Goal

修复 `./dev.sh stop` / `./dev.sh status` 在部分环境下的停机失败与误报问题，提升脚本健壮性：

1. **进程归属匹配过严**：`is_managed_process` 目前要求命令行精确包含 `${PROJECT_ROOT}.venv/bin/python`（绝对路径）。当服务以相对路径（`.venv/bin/py`）或 `python3 -m uvicorn` 等包装形式启动时，会被误判为「非本项目进程」，`stop` 拒绝并误报「端口被其他进程占用」，导致**无法停止自己的服务**。
2. **端口监听探测强依赖 `lsof`**：服务器/精简环境常未安装 `lsof`，导致 `stop`/`status` 的端口探测直接走不通。需增加 `ss`（Linux 备选）/ `fuser` 兜底。
3. **误导性报错**：无法归属时统一报「端口被其他进程占用」，未给用户诊断线索。

## Tech Stack

Bash 3+/macOS/Linux、Uvicorn `--reload`、`lsof`、`ss`、`fuser`、`ps`、pytest 子进程测试（沿用 `tests/test_dev_sh_daemon_controls.py` 的 fake `ps/lsof/curl/uv` 约定）。

---

## Task 1：为缺陷行为写失败测试

**Files:**

- Modify: `tests/test_dev_sh_daemon_controls.py`

- [ ] **Step 1**：新增fake `ps` 变体，返回相对路径/包装命令（如 `python3 -m uvicorn app.main:app --port 8123 --reload`），断言 `./dev.sh stop` 能识别为本项目 uvicorn 并停止、且 PID 文件被清理。当前实现将失败（视为「其他进程」拒绝）。
    失败断言要素：`returncode == 0`、输出含「后台服务已停止」、`.dev-server.pid` 被删除。

- [ ] **Step 2**：新增 fake bin **不提供 `lsof`、仅提供 `ss`** 的场景，断言 `./dev.sh status` / `./dev.sh stop` 仍能通过 `ss` 探测到监听 PID 并正确工作。当前实现将失败（`require_lsof` 直接返回）。

- [ ] **Step 3**：运行测试，确认上述用例在当前 `dev.sh` 下 FAIL（锁定缺陷）。

  ```bash
  venv/bin/python -m pytest "tests/test_dev_sh_daemon_controls.py::test_dev_sh_stop_matches_relative_python_cmd" \
    "tests/test_dev_sh_daemon_controls.py::test_dev_sh_probe_uses_ss_when_lsof_absent" \
    --confcutdir=tests -q
  ```

## Task 2：放宽进程归属匹配

**Files:**

- Modify: `dev.sh`

- [ ] **Step 1**：调整 `is_managed_process`，将强绝对路径匹配放宽为**该项目特征 + uvicorn 入口**匹配：
  - 同时包含 `uvicorn` 与 `app.main:app`；
  - 且匹配端口 `--port ${PORT}`；
  - 且**若出现 python 解释器路径，则接受 `.venv/[bin/]python` 或 `python`/`python3`**（兼容相对路径与包装脚本）；
  - 保留 `multiprocessing`（`--reload` worker）分支。
  - 加入对 `.venv` 路径倾向性判断：当命令行含 `.venv` 时才认作本项目，**降低误杀同机其他端口/同名 uvicorn 风险**（结合端口已限定，风险可控）。

- [ ] **Step 2**：`bash -n dev.sh` 校验通过。

## Task 3：端口监听探测增加 `ss` 兜底

**Files:**

- Modify: `dev.sh`

- [ ] **Step 1**：新增 `probe_listener_pids()`，按可用性依次尝试：
  1. `lsof -tiTCP:${PORT} -sTCP:LISTEN`
  2. `ss -ltnH "sport = :${PORT}"`（Linux，解析 `pid=` 字段；macOS 无 `-H` 需适配）
  3. `fuser ${PORT}/tcp 2>/dev/null`

- [ ] **Step 2**：`require_lsof` 改为 `require_port_probe`（任一探测工具可用即通过）；`get_port_pids` 改用 `probe_listener_pids`。返回码语义保持：0=有输出；可探测且无监听=空；无法探测=2。

- [ ] **Step 3**：`bash -n` 校验通过。

## Task 4：改进误导性报错

**Files:**

- Modify: `dev.sh`

- [ ] **Step 1**：`stop_service`/`status_service` 在「端口有监听但无法归属为受管服务」时，输出定位信息：监听 PID、进程命令摘要，并提示「若此为当前项目 uvicorn（如以相对路径/别名启动），请在 `.env` 确认后在控制台核对命令，或以 `kill <PID>` 手动停止」。避免仅笼统提示「被其他进程占用」。

- [ ] **Step 2**：`bash -n` 校验通过。

## Task 5：全量回归与提交准备

**Files:**

- Modify: `tests/CHECKLIST.md`、`DEVELOPMENT.md`/`README.md`（如需说明 ss 兜底与匹配放宽）

- [ ] **Step 1**：运行
  ```bash
  venv/bin/python -m pytest "tests/test_dev_sh_daemon_controls.py" "tests/test_dev_sh_python_bootstrap.py" --confcutdir=tests -q
  bash -n dev.sh
  ```
  全部通过。

- [ ] **Step 2**：更新 `tests/CHECKLIST.md` 验收清单，说明归属匹配放宽、`ss` 兜底、报错改进。

- [ ] **Step 3**：不自动提交；把改动交由用户 review/提交。

---

## Notes / 边界

- **安全权衡**：放宽归属匹配伴随误杀风险，用「端口 + `.venv` 倾向 + uvicorn 入口」三重约束来控制，避免误停同机无关进程。
- **macOS vs Linux**：`ss` 只有 Linux 有；macOS 仍在 `lsof`/`fuser` 路径下工作，需保证 `ss` 探测对 macOS 不产生 false 影响（用 `command -v ss` 判断，不可用则跳过）。
- `kill` 停止仍走既有 `stop_managed_process`（TERM→超时 KILL→复核端口）。