#!/bin/bash
set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

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

# 1. 停止旧服务
echo -e "\n${YELLOW}🛑 [1/3] 正在检查并停止旧服务 (Port ${PORT})...${NC}"
PID=$(lsof -ti:${PORT} || true)
if [ -n "$PID" ]; then
    kill -9 $PID
    echo -e "${GREEN}✅ 已停止旧进程 (PID: $PID)${NC}"
else
    echo -e "${GREEN}✅ 端口 ${PORT} 空闲，无需停止${NC}"
fi

# 2. 编译前端
echo -e "\n${YELLOW}🚀 [2/3] 正在编译前端 (Building Frontend)...${NC}"
if [ -d "frontend" ]; then
    cd frontend

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

# 3. 启动后端
# 确定 Python 环境
if [ -f "venv/bin/python" ]; then
    PYTHON_CMD="venv/bin/python"
else
    PYTHON_CMD="python3"
fi

# 热重载监听目录设置
RELOAD_ARGS=(--reload --reload-dir app)
if [ -d "architech" ]; then
    RELOAD_ARGS+=(--reload-dir architech)
fi

if [ "$DAEMON_MODE" = true ]; then
    echo -e "\n${YELLOW}🔥 [3/3] 正在后台启动后端服务 (Starting Backend in Daemon Mode)...${NC}"
    nohup $PYTHON_CMD -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" "${RELOAD_ARGS[@]}" > server.log 2>&1 &
    SERVER_PID=$!
    echo -e "${GREEN}✅ 后端服务已在后台启动！${NC}"
    echo -e "${BLUE}   ➜ 服务 PID: ${SERVER_PID}${NC}"
    echo -e "${BLUE}   ➜ 访问端口: http://0.0.0.0:${PORT}${NC}"
    echo -e "${BLUE}   ➜ 日志文件: server.log${NC}"
    echo -e "${YELLOW}   ➜ 查看实时日志命令: tail -f server.log${NC}"
else
    echo -e "\n${YELLOW}🔥 [3/3] 正在前台启动后端服务 (Starting Backend on Port ${PORT} in Foreground)...${NC}"
    echo -e "${BLUE}提示：您将在此看到实时运行日志，按 Ctrl+C 可停止服务；后台运行请使用: ./dev.sh -d${NC}"
    echo "------------------------------------------------"
    $PYTHON_CMD -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" "${RELOAD_ARGS[@]}"
fi
