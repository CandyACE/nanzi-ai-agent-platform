# dev.sh Python 3.11 自动环境引导设计

## 背景

当前 `dev.sh` 只在仓库已有 `venv/bin/python` 时使用虚拟环境，否则回退到系统
`python3`。这会导致新用户需要先手动安装 Python、创建虚拟环境并安装
`requirements.txt`，且系统 Python 版本可能不符合项目运行要求。

## 目标与边界

目标是让 macOS/Linux 用户首次执行 `./dev.sh` 时，自动完成以下 Python 侧准备：

1. 检查并准备 `uv`；缺少时使用 uv 官方安装脚本安装。
2. 准备 Python 3.11；缺少时由 uv 下载管理版本。
3. 创建或重建项目根目录下的 `.venv`。
4. 使用清华 PyPI 镜像安装 `requirements.txt`，并在依赖文件未变化时跳过重复安装。
5. 使用 `.venv/bin/python` 启动后端，避免依赖当前 shell 的激活状态。

本次不自动安装 Node.js/npm，不创建或修改数据库，不启动或配置 Redis，不生成
`.env`，也不改变 Docker/Kubernetes 启动路径。uv 安装和 Python/依赖下载均需要
网络；失败时脚本必须明确报错并退出。

## 方案

### uv 引导

脚本首先检测 PATH 中的 `uv`。找不到时，按 macOS/Linux 顺序检测 `curl` 或
`wget`，执行 uv 官方安装入口，并在当前脚本进程中重新定位安装后的可执行文件，
不依赖用户重新打开终端或加载 shell profile。若安装工具或网络不可用，输出修复
提示后退出。

不在脚本中固定 uv 版本；Python 版本固定为 `3.11`，以满足项目运行时约束。

### 虚拟环境

`.venv` 是新的标准环境，保留已有 `venv` 文件，不删除也不再优先使用它。脚本
检查 `.venv/bin/python` 的主次版本：

- 缺少 `.venv` 或其中没有可执行 Python 时，执行 `uv python install 3.11` 和
  `uv venv --python 3.11 .venv`。
- 已有 `.venv` 但 Python 不是 3.11 时，使用 uv 的清理/重建能力重建 `.venv`，
  不执行针对仓库其他目录的删除操作。
- 已有正确的 Python 3.11 环境时直接复用。

脚本不依赖 `source .venv/bin/activate`；通过绝对的项目相对路径调用解释器，避免
后台模式、子进程和非交互 shell 下的激活状态差异。

### 依赖安装

使用 `uv pip install --python .venv/bin/python` 安装依赖，索引地址默认是
`https://pypi.tuna.tsinghua.edu.cn/simple`，并允许通过 `PYPI_INDEX_URL` 覆盖。

脚本以 `cksum requirements.txt` 生成轻量标记，保存到 `.venv` 内，仅在标记缺失
或校验值变化时安装。只有依赖安装成功后才写入新标记；中途失败不会留下成功
状态。这样重复启动不会无条件重新解析和下载依赖，同时依赖文件变化会触发更新。

### 启动顺序

启动流程调整为四个阶段：

1. 准备 uv、Python 3.11、`.venv` 和 Python 依赖。
2. 检查并停止旧后端进程。
3. 安装/校验前端依赖并构建前端。
4. 使用 `.venv/bin/python` 启动 Uvicorn。

Python 环境准备放在停止旧服务之前，避免新环境准备失败时先把原有可用服务停掉。

## 错误处理

- 缺少 `uv` 且 `curl`/`wget` 均不存在：提示安装 uv 的方式并退出。
- uv 安装失败、Python 下载失败、虚拟环境创建失败或依赖安装失败：输出对应阶段
  和日志建议，返回非零状态。
- `requirements.txt` 不存在：明确指出仓库文件缺失并退出。
- Node/npm 缺失或前端构建失败：保留现有失败语义并退出，不回退到系统 Python。
- 不对 `.venv` 之外的路径执行清理；已有 `venv` 保留，便于用户手动回退。

## 文档与验证

同步更新 `README.md`、`README_EN.md` 和 `DEVELOPMENT.md`，将一键启动说明改为
Python 环境自动准备，并保留手动分步启动作为可选方式。

验证范围包括：

- `bash -n dev.sh`。
- 使用临时 fake `uv`/fake 安装结果覆盖 uv 已存在、uv 缺失、环境缺失、依赖标记
  命中和依赖标记失效等分支，不执行真实服务启动。
- 检查 `dev.sh` 的差异和 `git diff --check`。
- 不运行 `./dev.sh`，因此不宣称真实 Python 下载、镜像连通性、前端构建、数据库、
  Redis 或 Uvicorn 启动已验证。

