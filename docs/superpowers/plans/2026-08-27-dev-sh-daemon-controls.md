# dev.sh 后台服务生命周期命令 Implementation Plan

> **For agentic workers:** 按本计划逐项执行；实现过程中不启动真实服务，不自动提交。

**Goal:** 为 `./dev.sh -d` 增加可靠的 `status` 与 `stop` 命令，形成后台开发服务的启动、检查、停止闭环。

**Architecture:** `dev.sh` 在解析参数后先读取端口并分流 `status`/`stop`，这两个命令不执行 Python 环境准备、npm 安装或前端构建。后台启动将受管 Uvicorn PID 写入项目根目录的 `.dev-server.pid`；状态检查同时核对 PID 存活、Uvicorn 命令、端口监听和 `/health`，停止时优先优雅终止并在超时后强制终止，最后清理 PID 文件。

**Tech Stack:** Bash 3+/macOS/Linux、Uvicorn `--reload`、`lsof`、`ps`、`curl`、pytest 子进程测试。

---

## Task 1：生命周期命令失败测试

**Files:**

- Create: `tests/test_dev_sh_daemon_controls.py`

- [x] **Step 1：覆盖 status 分流与运行状态**

用临时仓库复制 `dev.sh`，写入 PID 文件并提供 fake `ps`、`lsof`、`curl`，断言 `./dev.sh status` 在不执行环境准备的情况下输出 PID、端口监听和健康状态。

- [x] **Step 2：覆盖 stop 优雅停止与清理**

启动临时 `sleep` 进程作为受测 PID，fake `ps` 将其识别为本项目 Uvicorn，执行 `./dev.sh stop`，断言进程退出、PID 文件删除，并且不会运行前端构建。

- [x] **Step 3：运行测试确认当前脚本缺少命令分流**

```bash
venv/bin/python -m pytest tests/test_dev_sh_daemon_controls.py --confcutdir=tests -q
```

已在实现前确认 FAIL：原因是当时 `dev.sh` 没有 `status`/`stop` 生命周期实现。

## Task 2：实现 PID 管理、状态检查和停止命令

**Files:**

- Modify: `dev.sh`
- Modify: `.gitignore`

- [x] **Step 1：解析端口与命令**

在环境准备前读取并校验 `API_SERVICE_PORT`，将 `status`、`stop` 与默认启动、`-d`/`--daemon` 分流；未知命令输出用法并返回非零。

- [x] **Step 2：实现受管 PID 文件与状态检查**

后台启动成功后写入 `.dev-server.pid`；`status` 校验 PID 存活、命令行包含 `uvicorn`/`app.main:app`、端口监听，并用 `curl` 检查 `/health`，分别报告不运行、端口未监听和健康失败。

- [x] **Step 3：实现安全停止**

`stop` 仅处理 PID 文件指向且命令校验通过的服务，先发送 `TERM`，最多等待 10 秒，仍存活再发送 `KILL`；停止后删除 PID 文件。兼容旧的无 PID 文件后台进程时，只提示端口占用，不直接误杀未知进程。

## Task 3：同步文档、测试清单和回归验证

**Files:**

- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `DEVELOPMENT.md`
- Modify: `tests/CHECKLIST.md`

补充前台、后台、状态、停止命令示例和真实验收边界；运行 `bash -n dev.sh`、6 项生命周期测试、3 项既有 dev.sh 引导测试及 `git diff --check`，不运行 `./dev.sh`。
