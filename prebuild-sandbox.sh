#!/bin/bash
# ==============================================================================
# NanZi AI 开源智能体平台 · Docker 沙箱镜像预构建运维脚本
# 用法:
#   ./prebuild-sandbox.sh                                     # 默认构建 (python:3.11-slim)
#   ./prebuild-sandbox.sh --proxy http://127.0.0.1:7890       # 带代理构建
#   ./prebuild-sandbox.sh --status                            # 仅检查预构建状态
#   ./prebuild-sandbox.sh --force                             # 强制重新构建
#   ./prebuild-sandbox.sh --base-image <镜像名>                # 指定基础镜像
# ==============================================================================
set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 脚本所在根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}       NanZi AI · Docker 安全沙箱镜像预构建与预热工具            ${NC}"
echo -e "${BLUE}================================================================${NC}"

# 寻找 Python 解释器（优先使用 venv / .venv）
PYTHON_BIN=""
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo -e "${RED}❌ 未找到可用的 Python 解释器，请先安装 Python 3.11+ 或配置虚拟环境！${NC}"
    exit 1
fi

echo -e "${GREEN}🐍 使用 Python 解释器: ${PYTHON_BIN}${NC}"

# 执行 Python 预构建运维脚本并透传所有参数
exec "$PYTHON_BIN" "$SCRIPT_DIR/scripts/prebuild_docker_sandbox.py" "$@"
