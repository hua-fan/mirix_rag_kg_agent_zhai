#!/bin/bash

# 启动翟助手前端和后端服务的脚本

# 显示欢迎信息
echo "========================================"
echo "        翟助手 前端服务启动脚本        "
echo "========================================"

# 检查Python环境
echo "检查Python环境..."
python --version || {
    echo "错误: 未找到Python，请先安装Python 3.7+"
    exit 1
}

# 安装依赖（如果需要）
if [ ! -f "../requirements.txt" ]; then
    echo "警告: 未找到requirements.txt文件，跳过依赖安装"
else
    echo "安装必要的依赖..."
    pip install -r ../requirements.txt
    pip install fastapi uvicorn
fi

# 启动API服务
echo "启动后端API服务..."
echo "服务将在 http://localhost:8000 上运行"
echo "API文档地址: http://localhost:8000/docs"
echo "按 Ctrl+C 停止服务"

# 启动uvicorn服务器
python api_server.py