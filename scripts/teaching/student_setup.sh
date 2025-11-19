#!/bin/bash

# CherryQuant 学生环境一键配置脚本
# 适用于 Module 0: 前置知识与环境搭建
# 支持平台: macOS, Linux (Ubuntu/Debian)

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# 检测操作系统
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查 Python 版本
check_python() {
    print_header "步骤 1: 检查 Python 版本"

    if command_exists python3.12; then
        PYTHON_CMD="python3.12"
    elif command_exists python3; then
        PYTHON_CMD="python3"
    else
        print_error "未找到 Python 3"
        return 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    print_info "检测到 Python $PYTHON_VERSION"

    if [[ $PYTHON_MAJOR -eq 3 ]] && [[ $PYTHON_MINOR -ge 12 ]]; then
        print_success "Python 版本符合要求 (3.12+)"
        return 0
    else
        print_error "Python 版本不符合要求，需要 3.12 或更高版本"
        print_warning "请先安装 Python 3.12+"

        OS=$(detect_os)
        if [[ "$OS" == "macos" ]]; then
            print_info "macOS 安装命令: brew install python@3.12"
        elif [[ "$OS" == "linux" ]]; then
            print_info "Ubuntu/Debian 安装命令:"
            echo "  sudo add-apt-repository ppa:deadsnakes/ppa"
            echo "  sudo apt update"
            echo "  sudo apt install python3.12 python3.12-venv"
        fi
        return 1
    fi
}

# 安装 uv 包管理器
install_uv() {
    print_header "步骤 2: 检查/安装 uv 包管理器"

    if command_exists uv; then
        UV_VERSION=$(uv --version 2>&1)
        print_success "uv 已安装: $UV_VERSION"
        return 0
    fi

    print_info "正在安装 uv 包管理器..."

    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        print_success "uv 安装成功"

        # 添加到当前 shell
        export PATH="$HOME/.cargo/bin:$PATH"

        print_warning "请运行以下命令使 uv 在当前 shell 生效:"
        echo "  export PATH=\"\$HOME/.cargo/bin:\$PATH\""
        print_info "或重新打开终端"
        return 0
    else
        print_error "uv 安装失败"
        print_info "请手动安装: https://github.com/astral-sh/uv"
        return 1
    fi
}

# 创建虚拟环境并安装依赖
setup_python_env() {
    print_header "步骤 3: 创建虚拟环境并安装依赖"

    if [[ ! -d ".venv" ]]; then
        print_info "创建虚拟环境..."
        uv venv
        print_success "虚拟环境创建完成"
    else
        print_success "虚拟环境已存在"
    fi

    print_info "安装项目依赖（可能需要几分钟）..."
    if uv sync; then
        print_success "依赖安装完成"
        return 0
    else
        print_error "依赖安装失败"
        return 1
    fi
}

# 配置环境变量
setup_env_file() {
    print_header "步骤 4: 配置环境变量"

    if [[ -f ".env" ]]; then
        print_warning ".env 文件已存在，跳过创建"
        print_info "如需重新配置，请手动删除 .env 文件后重新运行"
        return 0
    fi

    if [[ ! -f ".env.example" ]]; then
        print_error ".env.example 模板文件不存在"
        return 1
    fi

    print_info "从 .env.example 创建 .env 文件..."
    cp .env.example .env

    print_success ".env 文件创建完成"
    print_warning "请编辑 .env 文件，配置以下内容（根据需要）:"
    echo "  • LOG_LEVEL=INFO"
    echo "  • DEBUG=true"
    echo "  • TUSHARE_TOKEN=your_token  (Module 2 需要)"
    echo "  • OPENAI_API_KEY=sk-xxx     (Module 3 需要)"
    return 0
}

# 检查 Docker
check_docker() {
    print_header "步骤 5: 检查 Docker"

    if ! command_exists docker; then
        print_warning "Docker 未安装"
        print_info "Docker 用于运行 MongoDB 和 Redis 数据库"
        print_info "安装指南: https://docs.docker.com/get-docker/"

        OS=$(detect_os)
        if [[ "$OS" == "macos" ]]; then
            print_info "macOS: 下载 Docker Desktop"
            print_info "https://www.docker.com/products/docker-desktop/"
        elif [[ "$OS" == "linux" ]]; then
            print_info "Ubuntu/Debian 安装命令:"
            echo "  curl -fsSL https://get.docker.com | sh"
        fi
        return 1
    fi

    DOCKER_VERSION=$(docker --version)
    print_success "Docker 已安装: $DOCKER_VERSION"

    # 检查 Docker 是否运行
    if docker info >/dev/null 2>&1; then
        print_success "Docker 服务正在运行"
    else
        print_warning "Docker 服务未运行"
        print_info "请启动 Docker Desktop 或运行: sudo systemctl start docker"
        return 1
    fi

    # 检查 docker-compose
    if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
        print_success "docker-compose 已安装"
    else
        print_warning "docker-compose 未安装"
        return 1
    fi

    return 0
}

# 启动数据库服务
start_databases() {
    print_header "步骤 6: 启动数据库服务"

    if [[ ! -f "docker-compose.yml" ]]; then
        print_error "docker-compose.yml 文件不存在"
        return 1
    fi

    print_info "启动 MongoDB 和 Redis..."

    # 尝试使用 docker compose（新版本）
    if docker compose up -d mongodb redis 2>/dev/null; then
        print_success "数据库服务启动成功"
    # 回退到 docker-compose（旧版本）
    elif docker-compose up -d mongodb redis 2>/dev/null; then
        print_success "数据库服务启动成功"
    else
        print_error "数据库服务启动失败"
        print_info "请检查 Docker 是否正常运行"
        return 1
    fi

    print_info "等待数据库服务就绪（5 秒）..."
    sleep 5

    return 0
}

# 验证环境
verify_environment() {
    print_header "步骤 7: 验证环境配置"

    print_info "运行环境验证脚本..."

    if uv run python scripts/teaching/verify_environment.py; then
        return 0
    else
        print_warning "部分环境检查未通过"
        print_info "请根据上述提示修复问题"
        return 1
    fi
}

# 运行示例程序
run_hello_example() {
    print_header "步骤 8: 运行第一个示例"

    print_info "运行 Hello CherryQuant 示例..."

    if uv run python examples/01_basics/hello_cherryquant.py; then
        print_success "示例运行成功！"
        return 0
    else
        print_error "示例运行失败"
        return 1
    fi
}

# 主函数
main() {
    clear

    echo -e "${GREEN}"
    cat << "EOF"
   ____ _                          ___                  _
  / ___| |__   ___ _ __ _ __ _   _/ _ \ _   _  __ _ ___| |_
 | |   | '_ \ / _ \ '__| '__| | | | | | | | |/ _` / __| __|
 | |___| | | |  __/ |  | |  | |_| | |_| | |_| | (_| \__ \ |_
  \____|_| |_|\___|_|  |_|   \__, |\__\_\\__,_|\__,_|___/\__|
                             |___/
EOF
    echo -e "${NC}"

    print_header "CherryQuant 学生环境一键配置"

    print_info "本脚本将自动配置 CherryQuant 开发环境"
    print_info "适用于 Module 0: 前置知识与环境搭建"
    echo ""

    # 检查是否在项目根目录
    if [[ ! -f "pyproject.toml" ]] || [[ ! -d "src/cherryquant" ]]; then
        print_error "请在 CherryQuant 项目根目录运行此脚本"
        exit 1
    fi

    # 执行配置步骤
    check_python || exit 1
    install_uv || print_warning "跳过 uv 安装，请手动安装"
    setup_python_env || exit 1
    setup_env_file || print_warning ".env 配置可能需要手动调整"

    DOCKER_OK=0
    check_docker && start_databases && DOCKER_OK=1

    if [[ $DOCKER_OK -eq 0 ]]; then
        print_warning "Docker 相关步骤未完成，部分功能可能受限"
        print_info "可以先运行基础示例，后续再配置 Docker"
    fi

    # 最终验证
    print_header "🎉 环境配置完成！"

    echo -e "${GREEN}✅ 基础环境配置成功${NC}\n"

    print_info "下一步:"
    echo "  1. 编辑 .env 文件，配置必要的 API 密钥（可选）"
    echo "  2. 运行验证脚本: uv run python scripts/teaching/verify_environment.py"
    echo "  3. 运行第一个示例: uv run python examples/01_basics/hello_cherryquant.py"
    echo "  4. 阅读学习路径: cat LEARNING_PATH.md"
    echo "  5. 学习 Module 1: docs/course/01_System_Architecture.md"
    echo ""

    print_info "遇到问题？"
    echo "  • 查看文档: docs/course/00_Prerequisites.md"
    echo "  • 常见问题: examples/README.md"
    echo "  • 寻求帮助: 课程论坛或联系老师"
    echo ""

    print_success "祝学习愉快！🚀"
}

# 运行主函数
main
