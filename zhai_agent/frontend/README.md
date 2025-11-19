# 翟助手前端界面

这是翟助手的前端交互界面，提供了现代化的聊天体验。

## 功能特性

- 💬 实时聊天界面，支持发送和接收消息
- 🎨 现代化UI设计，响应式布局适应各种设备
- ⚡ 与后端API无缝集成
- 🔄 自动调整输入框高度
- ⏳ 显示正在输入状态指示
- 🔒 安全的HTML转义防止XSS攻击

## 文件结构

- `index.html` - 聊天界面的HTML结构
- `styles.css` - 界面样式和动画效果
- `script.js` - 前端交互逻辑
- `api_server.py` - 后端API服务（基于FastAPI）

## 快速开始

### 1. 安装依赖

首先确保安装了所有必要的Python依赖：

```bash
pip install fastapi uvicorn
```

### 2. 启动API服务

在前端目录下运行：

```bash
python api_server.py
```

服务将在 `http://localhost:8000` 上启动。

### 3. 打开聊天界面

直接在浏览器中打开 `index.html` 文件，或使用任何静态文件服务器提供访问。

### 4. API文档

启动服务后，可以访问以下URL查看API文档：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 使用说明

1. 在输入框中输入您的问题或消息
2. 点击"发送"按钮或按Enter键发送消息
3. 等待AI助手的回复

## 注意事项

- API服务需要与现有的 `WorkflowManager` 正确集成
- 确保 `WorkflowManager.process_user_request` 方法已更新以接受 `user_name` 参数
- 在生产环境中，应该配置具体的CORS来源，而不是使用 `*`
- 建议添加用户认证机制以提高安全性

## 开发说明

### 前端开发

前端使用纯HTML、CSS和JavaScript实现，无需额外的构建工具。您可以直接编辑文件进行开发。

### 后端开发

后端API使用FastAPI框架，支持自动重新加载（开发模式）。

## 故障排除

### API连接问题

如果前端无法连接到API服务：
1. 确认API服务正在运行
2. 检查浏览器控制台是否有CORS错误
3. 验证API端点URL是否正确

### 消息处理错误

如果消息处理失败：
1. 检查服务器日志获取详细错误信息
2. 验证 `WorkflowManager` 是否正确初始化
3. 确保所有必要的参数都正确传递

## 许可证

保留所有权利。