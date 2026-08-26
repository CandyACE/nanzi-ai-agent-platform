#!/bin/bash
set -e
set -o pipefail

# 确保从任意工作目录执行时都以项目根目录为基准
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Python 环境配置
PYTHON_VERSION="3.11"
VENV_DIR=".venv"
VENV_PYTHON="${VENV_DIR}/bin/python"
REQUIREMENTS_FILE="requirements.txt"
REQUIREMENTS_HASH_FILE="${VENV_DIR}/.requirements.hash"
PYPI_INDEX_URL="${PYPI_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
UV_CMD=""

# 查找已安装的 uv。官方安装器默认路径不一定已进入当前 shell 的 PATH，
# 因此额外检查常见的用户级安装目录。
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

# uv 不依赖 Python；若用户未安装 uv，则通过官方安装入口完成引导。
ensure_uv() {
    if find_uv; then
        return 0
    fi

    echo -e "${YELLOW}📦 未检测到 uv，正在通过官方安装脚本自动安装...${NC}"
    if command -v curl >/dev/null 2>&1; then
        if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
            echo -e "${RED}❌ uv 自动安装失败，请检查网络后重试${NC}" >&2
            return 1
        fi
    elif command -v wget >/dev/null 2>&1; then
        if ! wget -qO- https://astral.sh/uv/install.sh | sh; then
            echo -e "${RED}❌ uv 自动安装失败，请检查网络后重试${NC}" >&2
            return 1
        fi
    else
        echo -e "${RED}❌ 未找到 curl 或 wget，无法自动安装 uv；请先安装其中一个工具${NC}" >&2
        return 1
    fi

    if ! find_uv; then
        echo -e "${RED}❌ uv 安装完成但当前脚本无法定位 uv，请重新打开终端后重试${NC}" >&2
        return 1
    fi

    echo -e "${GREEN}✅ uv 已准备完成：${UV_CMD}${NC}"
}

# 准备 Python 3.11 虚拟环境及 requirements.txt 依赖。
prepare_python_environment() {
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        echo -e "${RED}❌ 错误：未找到 ${REQUIREMENTS_FILE}${NC}" >&2
        return 1
    fi

    ensure_uv
    echo -e "\n${YELLOW}🧰 [1/4] 正在准备 uv、Python ${PYTHON_VERSION} 和后端依赖...${NC}"

    current_version=""
    if [ -x "$VENV_PYTHON" ]; then
        current_version=$("$VENV_PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || true)
    fi

    if [ "$current_version" != "$PYTHON_VERSION" ]; then
        "$UV_CMD" python install "$PYTHON_VERSION"

        if [ -L "$VENV_DIR" ]; then
            echo -e "${RED}❌ 错误：${VENV_DIR} 是符号链接，拒绝自动清理${NC}" >&2
            return 1
        fi

        if [ -e "$VENV_DIR" ]; then
            echo -e "${YELLOW}♻️ 检测到 ${VENV_DIR} 不是 Python ${PYTHON_VERSION}，正在安全重建...${NC}"
            "$UV_CMD" venv --clear --python "$PYTHON_VERSION" "$VENV_DIR"
        else
            echo -e "${YELLOW}🐍 正在创建 Python ${PYTHON_VERSION} 虚拟环境...${NC}"
            "$UV_CMD" venv --python "$PYTHON_VERSION" "$VENV_DIR"
        fi
    else
        echo -e "${GREEN}✅ 已复用 Python ${PYTHON_VERSION} 虚拟环境${NC}"
    fi

    if [ ! -x "$VENV_PYTHON" ]; then
        echo -e "${RED}❌ Python 虚拟环境创建失败：未找到 ${VENV_PYTHON}${NC}" >&2
        return 1
    fi

    current_version=$("$VENV_PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || true)
    if [ "$current_version" != "$PYTHON_VERSION" ]; then
        echo -e "${RED}❌ Python 版本校验失败：期望 ${PYTHON_VERSION}，实际 ${current_version:-未知}${NC}" >&2
        return 1
    fi

    current_hash=$(cksum "$REQUIREMENTS_FILE" | awk '{print $1 ":" $2}')
    last_hash=""
    if [ -f "$REQUIREMENTS_HASH_FILE" ]; then
        last_hash=$(cat "$REQUIREMENTS_HASH_FILE")
    fi

    if [ "$current_hash" != "$last_hash" ]; then
        echo -e "${YELLOW}📦 正在使用清华 PyPI 镜像安装后端依赖...${NC}"
        "$UV_CMD" pip install --python "$VENV_PYTHON" --default-index "$PYPI_INDEX_URL" -r "$REQUIREMENTS_FILE"
        printf '%s\n' "$current_hash" > "$REQUIREMENTS_HASH_FILE"
        echo -e "${GREEN}✅ 后端依赖安装完成${NC}"
    else
        echo -e "${GREEN}✅ 后端依赖未变化，跳过安装${NC}"
    fi
}

# 启动模式解析（默认前台，传入 -d 或 --daemon 为后台）
DAEMON_MODE=false
for arg in "$@"; do
    if [ "$arg" == "-d" ] || [ "$arg" == "--daemon" ]; then
        DAEMON_MODE=true
    fi
done

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}       NanZi AI 开源智能体平台 · 本地开发启动工具         ${NC}"
echo -e "${BLUE}       用法: ./dev.sh (前台调试) | ./dev.sh -d (后台常驻) ${NC}"
echo -e "${BLUE}==================================================${NC}"

# 读取 .env 配置中的端口，默认 8001
PORT=8001
if [ -f ".env" ]; then
    ENV_PORT=$(grep -E "^[[:space:]]*API_SERVICE_PORT=" .env | tail -n 1 | cut -d '=' -f2 | tr -d ' "\r\n' || true)
    if [ -n "$ENV_PORT" ]; then
        PORT="$ENV_PORT"
    fi
fi

# 1. 准备 Python 环境
prepare_python_environment

# 2. 停止旧服务
echo -e "\n${YELLOW}🛑 [2/4] 正在检查并停止旧服务 (Port ${PORT})...${NC}"
PID=$(lsof -ti:${PORT} || true)
if [ -n "$PID" ]; then
    kill -9 $PID
    echo -e "${GREEN}✅ 已停止旧进程 (PID: $PID)${NC}"
else
    echo -e "${GREEN}✅ 端口 ${PORT} 空闲，无需停止${NC}"
fi

# 3. 编译前端
echo -e "\n${YELLOW}🚀 [3/4] 正在编译前端 (Building Frontend)...${NC}"
if [ -d "frontend" ]; then
    cd frontend

    if ! command -v npm >/dev/null 2>&1; then
        echo -e "${RED}❌ 错误：未找到 npm，请先安装 Node.js/npm${NC}" >&2
        exit 1
    fi
    if ! command -v npx >/dev/null 2>&1; then
        echo -e "${RED}❌ 错误：未找到 npx，请先安装 Node.js/npm${NC}" >&2
        exit 1
    fi

    # 自动检测前端依赖变更或缺失并执行安装
    CURRENT_HASH=$(cksum package.json 2>/dev/null || true)
    LAST_HASH=""
    if [ -f "node_modules/.package_hash" ]; then
        LAST_HASH=$(cat "node_modules/.package_hash" 2>/dev/null || true)
    fi

    if [ ! -d "node_modules" ] || [ "$CURRENT_HASH" != "$LAST_HASH" ]; then
        echo -e "${YELLOW}📦 检测到前端依赖变更或未安装，正在自动执行 npm install...${NC}"
        if npm install; then
            mkdir -p node_modules
            echo "$CURRENT_HASH" > node_modules/.package_hash
            echo -e "${GREEN}✅ 前端依赖安装完成！${NC}"
        else
            echo -e "${RED}❌ 前端依赖安装失败${NC}"
            exit 1
        fi
    fi

    # 优先使用 vite build (快)，如果需要完整类型检查可改回 npm run build
    if NODE_OPTIONS="--max-old-space-size=4096" npx vite build; then
        echo -e "${GREEN}✅ 前端编译成功！${NC}"
    else
        echo -e "${RED}❌ 前端编译失败${NC}"
        exit 1
    fi
    cd ..
else
    echo -e "${RED}❌ 错误：未找到 frontend 目录${NC}"
    exit 1
fi

# 4. 启动后端
PYTHON_CMD="$VENV_PYTHON"

# 热重载监听目录设置
RELOAD_ARGS=(--reload --reload-dir app)
if [ -d "architech" ]; then
    RELOAD_ARGS+=(--reload-dir architech)
fi

if [ "$DAEMON_MODE" = true ]; then
    echo -e "\n${YELLOW}🔥 [4/4] 正在后台启动后端服务 (Starting Backend in Daemon Mode)...${NC}"
    nohup "$PYTHON_CMD" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" "${RELOAD_ARGS[@]}" > server.log 2>&1 &
    SERVER_PID=$!
    echo -e "${GREEN}✅ 后端服务已在后台启动！${NC}"
    echo -e "${BLUE}   ➜ 服务 PID: ${SERVER_PID}${NC}"
    echo -e "${BLUE}   ➜ 访问端口: http://0.0.0.0:${PORT}${NC}"
    echo -e "${BLUE}   ➜ 日志文件: server.log${NC}"
    echo -e "${YELLOW}   ➜ 查看实时日志命令: tail -f server.log${NC}"
else
    echo -e "\n${YELLOW}🔥 [4/4] 正在前台启动后端服务 (Starting Backend on Port ${PORT} in Foreground)...${NC}"
    echo -e "${BLUE}提示：您将在此看到实时运行日志，按 Ctrl+C 可停止服务；后台运行请使用: ./dev.sh -d${NC}"
    echo "------------------------------------------------"
    "$PYTHON_CMD" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" "${RELOAD_ARGS[@]}"
fi
