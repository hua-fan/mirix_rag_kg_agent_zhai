from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sys
import os
import uuid
from fastapi import Header,Depends,HTTPException


SESSIONS = {}
# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入现有的workflow_manager
try:
    from zhai_agent.workflow.workflow_manager import WorkflowManager
except ImportError:
    print("无法导入WorkflowManager，请检查路径配置")
    exit(1)

# 创建FastAPI应用实例
app = FastAPI(
    title="翟助手 API",
    description="智能聊天助手后端API服务",
    version="1.0.0"
)

# 配置CORS以允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建WorkflowManager实例
workflow_manager = WorkflowManager()

# 定义请求和响应模型
class LoginRequest(BaseModel):
    username: str

class LoginResponse(BaseModel):
    success: bool
    user_name: str
    message: str
    token: str = ""

class ChatRequest(BaseModel):
    message: str
    

class ChatResponse(BaseModel):
    response: str
    success: bool
    user_name: str

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "翟助手 API"}

# 登录端点
@app.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    try:
        # 验证用户名
        if not request.username or not request.username.strip():
            return LoginResponse(
                success=False,
                user_name="",
                message="用户名不能为空"
            )
        
        if len(request.username) > 20:
            return LoginResponse(
                success=False,
                user_name="",
                message="用户名长度不能超过20个字符"
            )
        
        # 记录用户登录信息（这里只是打印，实际可以存储到数据库）
        print(f"用户登录: 用户名={request.username}")

        token = str(uuid.uuid4())

        SESSIONS[token] = {
            "user_name": request.username,
            "user_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, request.username))
        }
        
        return LoginResponse(
            success=True,
            user_name=request.username,
            message="登录成功",
            token=token
        )
        
    except Exception as e:
        print(f"处理登录请求时出错: {str(e)}")
        return LoginResponse(
            success=False,
            user_name="",
            message=f"登录失败: {str(e)}"
        )

async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少认证 Token")
    
    token = authorization.replace("Bearer ", "")
    user_data = SESSIONS.get(token)
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    return user_data

# 聊天端点
@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_data: dict = Depends(get_current_user)
):
    try:
        user_name = user_data["user_name"]
        user_id = user_data["user_id"]
        # 验证输入
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="消息内容不能为空")
        
        # 记录用户聊天信息（这里只是打印，实际可以存储到数据库）
        print(f"用户聊天: 用户名={request.user_name}, 会话ID={request.session_id}, 消息长度={len(request.message)}字符")
        
        # 调用现有的workflow_manager处理用户请求
        result = workflow_manager.process_user_request(
            user_message=request.message,
            user_name=user_name,
            session_id=user_id # 使用 user_id 作为 session_id
        )
        
        # 提取响应文本 - 处理可能的字典格式
        response_text = ""
        if isinstance(result, dict):
            # 如果是字典，尝试从messages中提取文本
            if 'messages' in result and isinstance(result['messages'], list) and result['messages']:
                response_text = result['messages'][-1].get('content', '')
            else:
                response_text = str(result)
        else:
            # 直接使用结果作为响应文本
            response_text = str(result)
        
        # 构建响应
        response = ChatResponse(
            response=response_text,
            success=True,
            user_name=request.user_name
        )
        
        return response
        
    except Exception as e:
        # 记录错误
        print(f"处理聊天请求时出错: {str(e)}")
        # 返回错误响应
        return ChatResponse(
            response=f"抱歉，处理您的请求时出现错误: {str(e)}",
            success=False,
            user_name=request.user_name
        )

# 配置静态文件服务
app.mount("/", StaticFiles(directory=".", html=True), name="static")

# API文档路径
@app.get("/api")
async def api_root():
    return {
        "message": "欢迎使用翟助手 API",
        "docs": "/docs",
        "redoc": "/redoc"
    }

# 启动命令
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )