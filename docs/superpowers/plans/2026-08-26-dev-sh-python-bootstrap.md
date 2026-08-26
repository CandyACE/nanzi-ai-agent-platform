# dev.sh Python 3.11 自动环境引导 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `./dev.sh` 自动准备 uv、Python 3.11、`.venv` 和后端依赖，并固定使用该环境启动后端。

**Architecture:** 在 `dev.sh` 启动流程最前面增加 Python 环境引导函数：先定位或安装 uv，再校验/创建 `.venv`，最后按 `requirements.txt` 校验值决定是否安装依赖。脚本不依赖 shell 激活状态，后端始终通过 `.venv/bin/python` 执行；Python 引导失败发生在停止旧服务之前。

**Tech Stack:** Bash 3+/macOS/Linux、uv、Python 3.11、pytest 子进程测试、Markdown 文档。

---

## 文件结构

- Modify: `/Users/chenxiaolong/workspace/nanzi-ai-agent-platform/dev.sh`：新增 uv/Python/依赖引导，调整启动阶段编号和后端解释器。
- Create: `/Users/chenxiaolong/workspace/nanzi-ai-agent-platform/tests/test_dev_sh_python_bootstrap.py`：用临时仓库、fake uv 和 fake 外部命令验证首次引导、重复启动和错误环境重建。
- Modify: `/Users/chenxiaolong/workspace/nanzi-ai-agent-platform/README.md`：说明一键脚本自动准备 Python 环境及仍需的外部前置条件。
- Modify: `/Users/chenxiaolong/workspace/nanzi-ai-agent-platform/README_EN.md`：同步英文一键启动说明。
- Modify: `/Users/chenxiaolong/workspace/nanzi-ai-agent-platform/DEVELOPMENT.md`：更新环境搭建、启动阶段和输出示例。
- Modify: `/Users/chenxiaolong/workspace/nanzi-ai-agent-platform/tests/CHECKLIST.md`：登记 dev.sh 自动环境引导的测试覆盖。

## Task 1: 添加失败的 dev.sh 自动引导回归测试

**Files:**

- Create: `tests/test_dev_sh_python_bootstrap.py`

- [x] **Step 1: 创建临时 fake 运行环境测试工具**

测试文件使用 `tmp_path` 创建最小仓库副本，写入 `dev.sh`、`requirements.txt`、
`frontend/package.json`，并在临时 PATH 中提供 fake `curl`、`uv`、`npm`、`npx`、
`lsof` 和 `python3`。fake uv 记录参数；执行 `uv venv` 时创建可响应版本探测和
Uvicorn 启动的 fake `.venv/bin/python`。

```python
ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _prepare_fake_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    (repo / "frontend").mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()
    shutil.copy(ROOT / "dev.sh", repo / "dev.sh")
    (repo / "requirements.txt").write_text("example-package==1.0\n", encoding="utf-8")
    (repo / "frontend" / "package.json").write_text("{}\n", encoding="utf-8")
    return repo, fake_bin, home
```

- [x] **Step 2: 写首次引导失败测试**

测试设置 PATH 中没有 uv，fake curl 输出一个安装器，安装器把 fake uv 写入
`$HOME/.local/bin/uv`。执行复制后的脚本并断言：uv 安装器被调用、执行了
`python install 3.11`、执行了 `venv --python 3.11`、执行了依赖安装、创建了
`.venv/.requirements.hash`，且 stdout/stderr 包含“Python 环境”准备阶段。

```python
def test_dev_sh_bootstraps_uv_python_and_requirements_on_first_run(tmp_path: Path):
    repo, fake_bin, home = _prepare_fake_repo(tmp_path)
    _install_fake_commands(fake_bin, home, uv_in_path=False)

    result = _run_dev(repo, fake_bin, home)

    assert result.returncode == 0, result.stdout + result.stderr
    log = (home / "uv.log").read_text(encoding="utf-8")
    assert "python install 3.11" in log
    assert "venv" in log and "--python 3.11" in log
    assert "pip install" in log and "requirements.txt" in log
    assert (repo / ".venv" / ".requirements.hash").is_file()
```

- [x] **Step 3: 运行测试确认当前实现失败**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/test_dev_sh_python_bootstrap.py --noconftest -q`

Expected: FAIL because当前 `dev.sh` 不检查或安装 uv，不创建 `.venv`，也不执行
`uv pip install`。

- [x] **Step 4: 添加重复启动和错误版本环境测试**

增加两个独立测试：第二次执行同一临时仓库时断言 uv 的 pip install 记录仍只有一次；
预置一个 fake Python 3.13 的 `.venv/bin/python` 后执行时断言 uv 收到
`venv --clear --python 3.11`，最终环境版本探测为 3.11。

## Task 2: 实现 dev.sh 的 uv/Python/依赖引导

**Files:**

- Modify: `dev.sh:1-110`

- [x] **Step 1: 增加脚本根目录、uv 命令定位和失败处理**

在 `set -e` 后启用 `pipefail`，计算脚本所在仓库根目录并切换过去；定义
`PYTHON_VERSION=3.11`、`.venv`、依赖标记和可覆盖的 `PYPI_INDEX_URL`。实现
`find_uv` 和 `ensure_uv`：先查 PATH，再查官方安装器常见的用户 bin 路径；缺少
uv 时优先使用 curl、其次 wget，安装后重新定位，失败则返回非零状态并打印修复提示。

```bash
set -e
set -o pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

PYTHON_VERSION="3.11"
VENV_DIR=".venv"
VENV_PYTHON="${VENV_DIR}/bin/python"
REQUIREMENTS_FILE="requirements.txt"
REQUIREMENTS_HASH_FILE="${VENV_DIR}/.requirements.hash"
PYPI_INDEX_URL="${PYPI_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
UV_CMD=""

find_uv() {
    if command -v uv >/dev/null 2>&1; then
        UV_CMD="$(command -v uv)"
        return 0
    fi
    for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -x "$candidate" ]; then
            UV_CMD="$candidate"
            return 0
        fi
    done
    return 1
}
```

- [x] **Step 2: 增加 `.venv` 版本校验、重建和依赖标记逻辑**

实现 `prepare_python_environment`：检查依赖文件；若 `.venv/bin/python` 不是
3.11，调用 `uv python install 3.11` 和 `uv venv --clear --python 3.11 .venv`；
若环境不存在则调用 `uv python install 3.11` 和 `uv venv --python 3.11 .venv`。
拒绝清理 `.venv` 符号链接。通过 `cksum` 比较 requirements 标记，成功安装后
才写入新标记。

```bash
prepare_python_environment() {
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        echo -e "${RED}❌ 错误：未找到 ${REQUIREMENTS_FILE}${NC}" >&2
        return 1
    fi

    ensure_uv
    echo -e "\n${YELLOW}🧰 [1/4] 正在准备 uv、Python ${PYTHON_VERSION} 和后端依赖...${NC}"

    current_version=""
    if [ -x "$VENV_PYTHON" ]; then
        current_version=$("$VENV_PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    fi
    if [ "$current_version" != "$PYTHON_VERSION" ]; then
        "$UV_CMD" python install "$PYTHON_VERSION"
        if [ -L "$VENV_DIR" ]; then
            echo -e "${RED}❌ 错误：${VENV_DIR} 是符号链接，拒绝自动清理${NC}" >&2
            return 1
        fi
        if [ -e "$VENV_DIR" ]; then
            "$UV_CMD" venv --clear --python "$PYTHON_VERSION" "$VENV_DIR"
        else
            "$UV_CMD" venv --python "$PYTHON_VERSION" "$VENV_DIR"
        fi
    fi

    current_hash=$(cksum "$REQUIREMENTS_FILE" | awk '{print $1 ":" $2}')
    last_hash=""
    if [ -f "$REQUIREMENTS_HASH_FILE" ]; then
        last_hash=$(cat "$REQUIREMENTS_HASH_FILE")
    fi
    if [ "$current_hash" != "$last_hash" ]; then
        "$UV_CMD" pip install --python "$VENV_PYTHON" --default-index "$PYPI_INDEX_URL" -r "$REQUIREMENTS_FILE"
        printf '%s\n' "$current_hash" > "$REQUIREMENTS_HASH_FILE"
    else
        echo -e "${GREEN}✅ 后端依赖未变化，跳过安装${NC}"
    fi
}
```

- [x] **Step 3: 调用环境准备并切换后端解释器**

在停止端口进程之前调用 `prepare_python_environment`；删除旧的 `venv`/系统
`python3` 二选一逻辑，设置 `PYTHON_CMD="$VENV_PYTHON"`，并将阶段编号改为
`[2/4]`、`[3/4]`、`[4/4]`。所有后端命令用引号包住解释器路径。

## Task 3: 更新用户文档和测试清单

**Files:**

- Modify: `README.md:303-331`
- Modify: `README_EN.md:257-285`
- Modify: `DEVELOPMENT.md:58-140`
- Modify: `tests/CHECKLIST.md`

- [x] **Step 1: 更新中文 README 的一键启动与手动启动说明**

说明 `./dev.sh` 首次运行会自动安装 uv、准备 Python 3.11、创建 `.venv` 并安装
后端依赖；明确仍需 Node.js/npm、`.env`、Redis 和数据库。手动启动命令改为
`.venv/bin/python -m uvicorn`，并保留传统 `venv` 流程作为手动兼容方式。

- [x] **Step 2: 同步更新英文 README 和 DEVELOPMENT.md**

英文文档说明同样的自动化范围；`DEVELOPMENT.md` 将自动流程列为四阶段，并将
旧输出示例中的 `[1/3]`、`[2/3]`、`[3/3]` 更新为四阶段，同时说明网络失败、
Node/npm 缺失和服务依赖仍需用户处理。

- [x] **Step 3: 登记自动化测试覆盖**

在 `tests/CHECKLIST.md` 增加一条记录，列出 uv 已存在/缺失、首次创建、正确环境
复用、错误版本重建、依赖标记命中/失效和环境准备失败的覆盖范围。

## Task 4: 回归验证与收尾

**Files:**

- Verify: `dev.sh`, `tests/test_dev_sh_python_bootstrap.py`, changed Markdown files

- [x] **Step 1: 运行脚本语法和 focused pytest**

Run: `bash -n dev.sh`

Expected: exit code 0。

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/test_dev_sh_python_bootstrap.py --noconftest -q`

Expected: all dev.sh bootstrap tests pass。

- [x] **Step 2: 检查差异和仓库文件范围**

Run: `git diff --check -- dev.sh README.md README_EN.md DEVELOPMENT.md tests/CHECKLIST.md tests/test_dev_sh_python_bootstrap.py docs/superpowers/specs/2026-08-26-dev-sh-python-bootstrap-design.md docs/superpowers/plans/2026-08-26-dev-sh-python-bootstrap.md`

Expected: no whitespace errors；`git status --short` 中只出现本任务新增/修改文件，
已有 `docs/superpowers/plans/2026-08-26-k8s-deploy.md`、`docs/superpowers/specs/2026-08-26-k8s-deploy-design.md` 和 `k8s_deploy/` 保持原样。

- [x] **Step 3: 明确未验证边界**

不运行 `./dev.sh`、不启动服务、不安装真实 Python/依赖，不进行数据库或 Redis 操作。
最终报告只宣称 Bash 语法、fake 外部命令回归、文档契约和 diff 检查结果；真实 uv
官方安装器、Python 3.11 下载、清华镜像连通性、Node 构建和 Uvicorn 启动留给用户在
控制台验证。
