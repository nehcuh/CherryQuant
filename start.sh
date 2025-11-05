#!/bin/bash

# CherryQuant 启动脚本

set -e

echo "🍒 CherryQuant AI期货交易系统"
echo "================================"

# 检查uv是否安装
if ! command -v uv &> /dev/null; then
    echo "❌ uv未安装，请先安装uv: https://docs.astral.sh/uv/"
    exit 1
fi

# 检查Python版本
python_version=$(uv python list | grep "3.12" | head -n 1 | awk '{print $1}')
if [ -z "$python_version" ]; then
    echo "❌ 未找到Python 3.12，正在安装..."
    uv python install 3.12
fi

# 安装依赖
echo "📦 正在安装依赖..."
uv sync

# 检查环境变量
if [ ! -f ".env" ]; then
    echo "⚠️  .env文件不存在，正在创建..."
    cp .env.example .env
    echo "请编辑 .env 文件，设置您的 OpenAI API Key"
    echo "然后重新运行此脚本"
    exit 1
fi

# 检查OpenAI API Key
if ! grep -q "your_openai_api_key_here" .env; then
    echo "✅ OpenAI API Key已配置"
else
    echo "❌ 请在 .env 文件中设置您的 OpenAI API Key"
    exit 1
fi

# 选择运行模式
echo ""
echo "请选择运行模式："
echo "1. 模拟交易 (推荐)"
echo "2. 回测模式"
echo "3. 实盘模式 (需要期货账户)"
echo ""
read -p "请输入选择 (1-3): " choice

case $choice in
    1)
        echo "🚀 启动模拟交易模式..."
        uv run python run_cherryquant.py simulation
        ;;
    2)
        echo "📊 启动回测模式..."
        uv run python run_cherryquant.py backtest
        ;;
    3)
        echo "⚠️  警告：即将启动实盘交易模式"
        read -p "确认继续？(yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            echo "🚀 启动实盘模式..."
            uv run python run_cherryquant.py live
        else
            echo "已取消"
        fi
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac