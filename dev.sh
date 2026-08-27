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
MANAGED_PYTHON_CMD="${PROJECT_ROOT}/${VENV_PYTHON}"
REQUIREMENTS_FILE="requirements.txt"
REQUIREMENTS_HASH_FILE="${VENV_DIR}/.requirements.hash"
PYPI_INDEX_URL="${PYPI_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
UV_CMD=""
PID_FILE=".dev-server.pid"
SERVER_LOG_FILE="server.log"
HEALTH_PATH="/health"
STOP_TIMEOUT_SECONDS=10

# 读取 .env 中的非敏感配置值。仅用于打印连接类型和地址，不读取密码字段。
read_env_value() {
    key="$1"
    if [ ! -f ".env" ]; then
        return 0
    fi

    grep -E "^[[:space:]]*${key}[[:space:]]*=" ".env" \
        | tail -n 1 \
        | cut -d '=' -f 2- \
        | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//' \
        || true
}

redact_url() {
    printf '%s' "$1" | sed -E 's#(https?://)([^/@]+@)#\1***@#'
}

print_usage() {
    cat <<'EOF'
用法:
  ./dev.sh              前台启动开发服务
  ./dev.sh -d           后台启动开发服务
  ./dev.sh status       查看后台服务状态
  ./dev.sh stop         停止后台开发服务
EOF
}

parse_command_line() {
    COMMAND="start"
    DAEMON_MODE=false
    for arg in "$@"; do
        case "$arg" in
            -d|--daemon)
                if [ "$COMMAND" != "start" ]; then
                    echo -e "${RED}❌ status/stop 不能与后台启动参数同时使用${NC}" >&2
                    print_usage >&2
                    return 1
                fi
                DAEMON_MODE=true
                ;;
            status|stop)
                if [ "$COMMAND" != "start" ] || [ "$DAEMON_MODE" = true ]; then
                    echo -e "${RED}❌ 只能指定一个启动或生命周期命令${NC}" >&2
                    print_usage >&2
                    return 1
                fi
                COMMAND="$arg"
                ;;
            *)
                echo -e "${RED}❌ 未知参数：${arg}${NC}" >&2
                print_usage >&2
                return 1
                ;;
        esac
    done
}

read_configured_port() {
    PORT=8001
    if [ -f ".env" ]; then
        ENV_PORT=$(grep -E "^[[:space:]]*API_SERVICE_PORT[[:space:]]*=" ".env" \
            | tail -n 1 \
            | cut -d '=' -f 2- \
            | tr -d ' \"\r\n' || true)
        if [ -n "$ENV_PORT" ]; then
            PORT="$ENV_PORT"
        fi
    fi
}

validate_port() {
    if ! printf '%s' "$PORT" | grep -Eq '^[0-9]+$' || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
        echo -e "${RED}❌ API_SERVICE_PORT 无效：${PORT}（必须是 1-65535）${NC}" >&2
        return 1
    fi
}

is_process_alive() {
    if ! kill -0 "$1" 2>/dev/null; then
        return 1
    fi

    if ! command -v ps >/dev/null 2>&1; then
        return 2
    fi
    PROCESS_STATE=$(ps -p "$1" -o stat= 2>/dev/null | tr -d '[:space:]') || return 2
    if [ -z "$PROCESS_STATE" ]; then
        return 2
    fi
    case "$PROCESS_STATE" in
        Z*|z*)
            return 1
            ;;
    esac
    return 0
}

process_command() {
    if ! command -v ps >/dev/null 2>&1; then
        return 1
    fi
    ps -p "$1" -o command= 2>/dev/null | head -n 1
}

is_managed_process() {
    PROCESS_COMMAND=$(process_command "$1") || return 1
    case "$PROCESS_COMMAND" in
        *"$MANAGED_PYTHON_CMD"*uvicorn*app.main:app*--port*"$PORT"*)
            return 0
            ;;
        *"$MANAGED_PYTHON_CMD"*multiprocessing*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

get_port_pids() {
    if ! command -v lsof >/dev/null 2>&1; then
        return 2
    fi

    LSOF_STATUS=0
    LSOF_OUTPUT=$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null) || LSOF_STATUS=$?
    if [ "$LSOF_STATUS" -gt 1 ]; then
        return 2
    fi
    printf '%s\n' "$LSOF_OUTPUT"
}

require_lsof() {
    if ! command -v lsof >/dev/null 2>&1; then
        echo -e "${RED}❌ 未找到 lsof，无法安全检查端口占用${NC}" >&2
        return 1
    fi
}

require_ps() {
    if ! command -v ps >/dev/null 2>&1; then
        echo -e "${RED}❌ 未找到 ps，无法安全检查后台进程${NC}" >&2
        return 1
    fi
}

find_managed_listener_pid() {
    for listener_pid in $PORT_PIDS; do
        if is_process_alive "$listener_pid"; then
            PROCESS_STATUS=0
        else
            PROCESS_STATUS=$?
        fi
        if [ "$PROCESS_STATUS" -eq 0 ] && is_managed_process "$listener_pid"; then
            printf '%s\n' "$listener_pid"
            return 0
        fi
    done
    return 1
}

find_managed_listener_pids() {
    for listener_pid in $PORT_PIDS; do
        if is_process_alive "$listener_pid"; then
            PROCESS_STATUS=0
        else
            PROCESS_STATUS=$?
        fi
        if [ "$PROCESS_STATUS" -eq 0 ] && is_managed_process "$listener_pid"; then
            printf '%s\n' "$listener_pid"
        fi
    done
}

read_pid_file() {
    if [ ! -f "$PID_FILE" ]; then
        return 1
    fi

    SERVER_PID=""
    PID_PROJECT_ROOT=""
    PID_PORT=""
    PID_PYTHON=""
    if grep -q '^pid=' "$PID_FILE"; then
        SERVER_PID=$(sed -n 's/^pid=//p' "$PID_FILE" | sed -n '1p' | tr -d '[:space:]')
        PID_PROJECT_ROOT=$(sed -n 's/^project_root=//p' "$PID_FILE" | sed -n '1p')
        PID_PORT=$(sed -n 's/^port=//p' "$PID_FILE" | sed -n '1p' | tr -d '[:space:]')
        PID_PYTHON=$(sed -n 's/^python=//p' "$PID_FILE" | sed -n '1p')
    else
        # 兼容早期只写入数字 PID 的文件；进程命令仍必须通过绝对路径归属校验。
        SERVER_PID=$(sed -n '1p' "$PID_FILE" | tr -d '[:space:]')
    fi
    case "$SERVER_PID" in
        ''|*[!0-9]*)
            return 1
            ;;
    esac
    return 0
}

pid_file_matches_project() {
    if [ -n "$PID_PROJECT_ROOT" ] && [ "$PID_PROJECT_ROOT" != "$PROJECT_ROOT" ]; then
        return 1
    fi
    if [ -n "$PID_PORT" ] && [ "$PID_PORT" != "$PORT" ]; then
        return 1
    fi
    if [ -n "$PID_PYTHON" ] && [ "$PID_PYTHON" != "$MANAGED_PYTHON_CMD" ]; then
        return 1
    fi
    return 0
}

health_check() {
    if ! command -v curl >/dev/null 2>&1; then
        return 2
    fi
    curl -fsS --max-time 3 "http://127.0.0.1:${PORT}${HEALTH_PATH}" >/dev/null 2>&1
}

status_service() {
    validate_port || return 1
    require_lsof || return 1
    require_ps || return 1

    RUNNING_PID=""
    STALE_PID=false
    PORT_PIDS=""
    if ! PORT_PIDS=$(get_port_pids); then
        echo -e "${RED}❌ lsof 检查端口 ${PORT} 失败，无法确认后台服务状态${NC}" >&2
        return 1
    fi
    if read_pid_file; then
        if ! pid_file_matches_project; then
            echo -e "${RED}❌ PID 文件不属于当前项目，拒绝接管${NC}" >&2
            return 1
        fi
        if is_process_alive "$SERVER_PID"; then
            PROCESS_STATUS=0
        else
            PROCESS_STATUS=$?
        fi
        if [ "$PROCESS_STATUS" -eq 0 ] && is_managed_process "$SERVER_PID"; then
            RUNNING_PID="$SERVER_PID"
        elif [ "$PROCESS_STATUS" -eq 1 ]; then
            STALE_PID=true
            rm -f "$PID_FILE"
        elif [ "$PROCESS_STATUS" -eq 2 ]; then
            echo -e "${RED}❌ 无法确认 PID ${SERVER_PID} 的进程状态，拒绝接管${NC}" >&2
            return 1
        else
            echo -e "${RED}❌ PID 文件指向的进程不是本项目 Uvicorn，拒绝接管${NC}"
            return 1
        fi
    elif [ -f "$PID_FILE" ]; then
        STALE_PID=true
        rm -f "$PID_FILE"
    fi

    if [ -z "$RUNNING_PID" ]; then
        RUNNING_PID=$(find_managed_listener_pid || true)
    fi

    MANAGED_LISTENER_PID=$(find_managed_listener_pid || true)
    if [ -z "$MANAGED_LISTENER_PID" ]; then
        if [ -n "$PORT_PIDS" ]; then
            echo -e "${YELLOW}⚠️ 后台服务未受管，但端口 ${PORT} 被其他进程占用${NC}"
        else
            echo -e "${YELLOW}ℹ️ 后台服务未运行${NC}"
        fi
        if [ "$STALE_PID" = true ]; then
            echo -e "${YELLOW}   ➜ PID 文件已失效，已清理${NC}"
        fi
        return 1
    fi

    echo -e "${GREEN}✅ 后台服务正在运行${NC}"
    echo -e "${BLUE}   ➜ PID: ${RUNNING_PID}${NC}"

    echo -e "${GREEN}   ➜ 端口 ${PORT}: 已监听（PID: ${MANAGED_LISTENER_PID}）${NC}"

    if health_check; then
        echo -e "${GREEN}   ➜ 健康检查: 正常${NC}"
    else
        HEALTH_STATUS=$?
        if [ "$HEALTH_STATUS" -eq 2 ]; then
            echo -e "${RED}   ➜ 健康检查: 未检查（未找到 curl）${NC}"
            return 1
        else
            echo -e "${RED}   ➜ 健康检查: 失败（${HEALTH_PATH}）${NC}"
            return 1
        fi
    fi
}

wait_for_process_exit() {
    WAITED_SECONDS=0
    while :; do
        if is_process_alive "$1"; then
            PROCESS_STATUS=0
        else
            PROCESS_STATUS=$?
        fi
        case "$PROCESS_STATUS" in
            1)
                return 0
                ;;
            2)
                return 2
                ;;
        esac
        if [ "$WAITED_SECONDS" -ge "$STOP_TIMEOUT_SECONDS" ]; then
            return 1
        fi
        sleep 1
        WAITED_SECONDS=$((WAITED_SECONDS + 1))
    done
}

stop_managed_process() {
    TARGET_PID="$1"
    if is_process_alive "$TARGET_PID"; then
        PROCESS_STATUS=0
    else
        PROCESS_STATUS=$?
    fi
    if [ "$PROCESS_STATUS" -eq 1 ]; then
        return 0
    fi
    if [ "$PROCESS_STATUS" -eq 2 ]; then
        echo -e "${RED}❌ 无法确认 PID ${TARGET_PID} 的进程状态，拒绝停止${NC}" >&2
        return 1
    fi
    if ! is_managed_process "$TARGET_PID"; then
        echo -e "${RED}❌ PID ${TARGET_PID} 不是本项目 Uvicorn，拒绝停止${NC}" >&2
        return 1
    fi

    echo -e "${YELLOW}🛑 正在停止后台服务 (PID: ${TARGET_PID})...${NC}"
    kill -TERM "$TARGET_PID" 2>/dev/null || true
    if wait_for_process_exit "$TARGET_PID"; then
        return 0
    else
        WAIT_STATUS=$?
    fi
    if [ "$WAIT_STATUS" -eq 2 ]; then
        echo -e "${RED}❌ 无法确认 PID ${TARGET_PID} 是否已退出${NC}" >&2
        return 1
    fi
    if [ "$WAIT_STATUS" -eq 1 ]; then
        echo -e "${YELLOW}⚠️ 优雅停止超时，正在强制停止 PID ${TARGET_PID}${NC}"
        kill -KILL "$TARGET_PID" 2>/dev/null || true
    fi

    if wait_for_process_exit "$TARGET_PID"; then
        return 0
    else
        WAIT_STATUS=$?
    fi
    if [ "$WAIT_STATUS" -eq 2 ] || [ "$WAIT_STATUS" -eq 1 ]; then
        echo -e "${RED}❌ 无法停止后台服务 PID ${TARGET_PID}${NC}" >&2
        return 1
    fi
}

stop_service() {
    validate_port || return 1
    require_lsof || return 1
    require_ps || return 1

    PORT_PIDS=""
    if ! PORT_PIDS=$(get_port_pids); then
        echo -e "${RED}❌ lsof 检查端口 ${PORT} 失败，拒绝停止${NC}" >&2
        return 1
    fi

    TARGET_PIDS=""
    if read_pid_file; then
        if ! pid_file_matches_project; then
            echo -e "${RED}❌ PID 文件不属于当前项目，拒绝停止${NC}" >&2
            return 1
        fi
        if is_process_alive "$SERVER_PID"; then
            PROCESS_STATUS=0
        else
            PROCESS_STATUS=$?
        fi
        if [ "$PROCESS_STATUS" -eq 0 ]; then
            if ! is_managed_process "$SERVER_PID"; then
                echo -e "${RED}❌ PID 文件指向的进程不是本项目 Uvicorn，拒绝停止${NC}" >&2
                return 1
            fi
            TARGET_PIDS="$SERVER_PID"
        elif [ "$PROCESS_STATUS" -eq 1 ]; then
            echo -e "${YELLOW}⚠️ PID 文件已失效，正在清理${NC}"
            rm -f "$PID_FILE"
        else
            echo -e "${RED}❌ 无法确认 PID ${SERVER_PID} 的进程状态，拒绝停止${NC}" >&2
            return 1
        fi
    elif [ -f "$PID_FILE" ]; then
        rm -f "$PID_FILE"
    fi

    if [ -z "$TARGET_PIDS" ]; then
        TARGET_PIDS=$(find_managed_listener_pid || true)
    fi

    if [ -z "$TARGET_PIDS" ]; then
        if ! require_lsof; then
            return 1
        fi
        if [ -n "$(get_port_pids)" ]; then
            echo -e "${RED}❌ 未找到受管后台服务；端口 ${PORT} 被其他进程占用，未执行停止${NC}" >&2
            return 1
        fi
        rm -f "$PID_FILE"
        echo -e "${YELLOW}ℹ️ 后台服务未运行${NC}"
        return 0
    fi

    STOP_FAILED=false
    for target_pid in $TARGET_PIDS; do
        if ! stop_managed_process "$target_pid"; then
            STOP_FAILED=true
        fi
    done
    if [ "$STOP_FAILED" = true ]; then
        return 1
    fi

    PORT_PIDS=""
    if ! PORT_PIDS=$(get_port_pids); then
        echo -e "${RED}❌ 停止后无法复核端口 ${PORT}${NC}" >&2
        return 1
    fi
    EXTRA_PIDS=$(find_managed_listener_pids || true)
    for extra_pid in $EXTRA_PIDS; do
        if ! stop_managed_process "$extra_pid"; then
            STOP_FAILED=true
        fi
    done
    if [ "$STOP_FAILED" = true ]; then
        return 1
    fi

    PORT_PIDS=""
    if ! PORT_PIDS=$(get_port_pids); then
        echo -e "${RED}❌ 停止后无法复核端口 ${PORT}${NC}" >&2
        return 1
    fi
    if [ -n "$PORT_PIDS" ]; then
        echo -e "${RED}❌ 停止后端口 ${PORT} 仍被占用，未报告为已停止${NC}" >&2
        return 1
    fi

    rm -f "$PID_FILE"
    echo -e "${GREEN}✅ 后台服务已停止${NC}"
}

stop_previous_service() {
    stop_service
}

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
        "$UV_CMD" pip check --python "$VENV_PYTHON"
        echo -e "${GREEN}✅ 后端依赖未变化且环境检查通过，跳过安装${NC}"
    fi
}

# 启动模式解析（默认前台，传入 -d 或 --daemon 为后台）
parse_command_line "$@" || exit 1
read_configured_port
validate_port || exit 1

# 生命周期命令必须在环境准备、依赖安装和前端构建之前直接返回。
if [ "$COMMAND" = "status" ]; then
    status_service
    exit $?
fi
if [ "$COMMAND" = "stop" ]; then
    stop_service
    exit $?
fi

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}       NanZi AI 开源智能体平台 · 本地开发启动工具         ${NC}"
echo -e "${BLUE}       用法: ./dev.sh (前台) | ./dev.sh -d (后台) | status | stop ${NC}"
echo -e "${BLUE}==================================================${NC}"

echo -e "${BLUE}       启动环境信息${NC}"
if find_uv; then
    UV_VERSION=$("$UV_CMD" --version 2>/dev/null || echo "版本未知")
else
    UV_VERSION="未安装（启动时自动安装）"
fi
echo -e "${BLUE}       ➜ uv: ${UV_VERSION}${NC}"
echo -e "${BLUE}       ➜ Python 目标版本: ${PYTHON_VERSION}${NC}"
echo -e "${BLUE}       ➜ 虚拟环境: ${VENV_DIR}${NC}"
echo -e "${BLUE}       ➜ PyPI 镜像: $(redact_url "$PYPI_INDEX_URL")${NC}"

# 打印实际采用的数据库/Redis 连接位置，但不输出用户名、密码等敏感信息。
print_runtime_environment() {
    DATABASE_TYPE_CONFIGURED="${DATABASE_TYPE:-$(read_env_value DATABASE_TYPE)}"
    if [ -z "$DATABASE_TYPE_CONFIGURED" ]; then
        DATABASE_TYPE_CONFIGURED="mysql"
    fi

    DATABASE_TYPE_NORMALIZED=$(printf '%s' "$DATABASE_TYPE_CONFIGURED" | tr '[:upper:]' '[:lower:]')
    case "$DATABASE_TYPE_NORMALIZED" in
        postgres|postgresql|pg)
            DATABASE_TYPE_EFFECTIVE="postgresql"
            DATABASE_HOST="${POSTGRES_HOST:-$(read_env_value POSTGRES_HOST)}"
            DATABASE_PORT="${POSTGRES_PORT:-$(read_env_value POSTGRES_PORT)}"
            DATABASE_NAME="${POSTGRES_DB:-$(read_env_value POSTGRES_DB)}"
            DATABASE_HOST="${DATABASE_HOST:-localhost}"
            DATABASE_PORT="${DATABASE_PORT:-5432}"
            ;;
        mysql|mariadb)
            DATABASE_TYPE_EFFECTIVE="mysql"
            DATABASE_HOST="${MYSQL_HOST:-$(read_env_value MYSQL_HOST)}"
            DATABASE_PORT="${MYSQL_PORT:-$(read_env_value MYSQL_PORT)}"
            DATABASE_NAME="${MYSQL_DB:-$(read_env_value MYSQL_DB)}"
            DATABASE_HOST="${DATABASE_HOST:-未配置}"
            DATABASE_PORT="${DATABASE_PORT:-3306}"
            ;;
        *)
            DATABASE_TYPE_EFFECTIVE="unsupported"
            DATABASE_HOST="未配置"
            DATABASE_PORT="未配置"
            DATABASE_NAME="未配置"
            ;;
    esac
    DATABASE_NAME="${DATABASE_NAME:-未配置}"

    REDIS_HOST_CONFIGURED="${REDIS_HOST:-$(read_env_value REDIS_HOST)}"
    REDIS_PORT_CONFIGURED="${REDIS_PORT:-$(read_env_value REDIS_PORT)}"
    REDIS_DB_CONFIGURED="${REDIS_DB:-$(read_env_value REDIS_DB)}"
    REDIS_ENABLE_CONFIGURED="${REDIS_ENABLE:-$(read_env_value REDIS_ENABLE)}"
    REDIS_HOST_CONFIGURED="${REDIS_HOST_CONFIGURED:-未配置}"
    REDIS_PORT_CONFIGURED="${REDIS_PORT_CONFIGURED:-6379}"
    REDIS_DB_CONFIGURED="${REDIS_DB_CONFIGURED:-0}"
    REDIS_ENABLE_CONFIGURED=$(printf '%s' "${REDIS_ENABLE_CONFIGURED:-true}" | tr '[:upper:]' '[:lower:]')

    echo -e "${BLUE}       ➜ DATABASE_TYPE: ${DATABASE_TYPE_CONFIGURED} (effective: ${DATABASE_TYPE_EFFECTIVE})${NC}"
    echo -e "${BLUE}       ➜ 数据库地址: ${DATABASE_HOST}:${DATABASE_PORT}/${DATABASE_NAME}${NC}"
    if [ "$REDIS_ENABLE_CONFIGURED" = "false" ] || [ "$REDIS_ENABLE_CONFIGURED" = "0" ] || [ "$REDIS_ENABLE_CONFIGURED" = "no" ] || [ "$REDIS_ENABLE_CONFIGURED" = "off" ]; then
        echo -e "${BLUE}       ➜ Redis 地址: 已禁用${NC}"
    else
        echo -e "${BLUE}       ➜ Redis 地址: ${REDIS_HOST_CONFIGURED}:${REDIS_PORT_CONFIGURED}/${REDIS_DB_CONFIGURED}${NC}"
    fi
}

print_runtime_environment

# 1. 准备 Python 环境
prepare_python_environment

# 2. 停止旧服务
echo -e "\n${YELLOW}🛑 [2/4] 正在检查并停止旧服务 (Port ${PORT})...${NC}"
if ! stop_previous_service; then
    exit 1
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
PYTHON_CMD="$MANAGED_PYTHON_CMD"

# 热重载监听目录设置
RELOAD_ARGS=(--reload --reload-dir app)
if [ -d "architech" ]; then
    RELOAD_ARGS+=(--reload-dir architech)
fi

if [ "$DAEMON_MODE" = true ]; then
    echo -e "\n${YELLOW}🔥 [4/4] 正在后台启动后端服务 (Starting Backend in Daemon Mode)...${NC}"
    nohup "$PYTHON_CMD" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" "${RELOAD_ARGS[@]}" > "$SERVER_LOG_FILE" 2>&1 &
    SERVER_PID=$!
    if ! {
        printf 'pid=%s\n' "$SERVER_PID"
        printf 'project_root=%s\n' "$PROJECT_ROOT"
        printf 'port=%s\n' "$PORT"
        printf 'python=%s\n' "$MANAGED_PYTHON_CMD"
    } > "$PID_FILE"; then
        kill -TERM "$SERVER_PID" 2>/dev/null || true
        echo -e "${RED}❌ 无法写入后台服务 PID 文件：${PID_FILE}${NC}" >&2
        exit 1
    fi
    sleep 1
    if ! is_process_alive "$SERVER_PID"; then
        rm -f "$PID_FILE"
        echo -e "${RED}❌ 后台服务启动进程未能保持运行，请检查 ${SERVER_LOG_FILE}${NC}" >&2
        exit 1
    fi
    echo -e "${GREEN}✅ 后端服务已在后台启动！${NC}"
    echo -e "${BLUE}   ➜ 服务 PID: ${SERVER_PID}${NC}"
    echo -e "${BLUE}   ➜ 访问端口: http://0.0.0.0:${PORT}${NC}"
    echo -e "${BLUE}   ➜ PID 文件: ${PID_FILE}${NC}"
    echo -e "${BLUE}   ➜ 日志文件: ${SERVER_LOG_FILE}${NC}"
    echo -e "${YELLOW}   ➜ 查看实时日志命令: tail -f ${SERVER_LOG_FILE}${NC}"
else
    echo -e "\n${YELLOW}🔥 [4/4] 正在前台启动后端服务 (Starting Backend on Port ${PORT} in Foreground)...${NC}"
    echo -e "${BLUE}提示：您将在此看到实时运行日志，按 Ctrl+C 可停止服务；后台运行请使用: ./dev.sh -d${NC}"
    echo "------------------------------------------------"
    "$PYTHON_CMD" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" "${RELOAD_ARGS[@]}"
fi
