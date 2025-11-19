from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sys
import os
import uuid
from fastapi import Header,Depends,HTTPException
import json
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage


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

# 聊天端点（流式输出版）
@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    user_data: dict = Depends(get_current_user)
):
    try:
        user_name = user_data["user_name"]
        user_id = user_data["user_id"]
        
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="消息内容不能为空")
            
        print(f"用户聊天: 用户名={user_name}, 消息={request.message[:20]}...")

        # 定义流式生成器
        async def event_stream():
            # 1. 确保工作流已初始化
            if workflow_manager.app is None:
                workflow_manager.create_workflow()

            # 2. 构建输入
            inputs = {
                "messages": [HumanMessage(content=request.message)],
                "user_name": user_name,
                "session_id": user_id,
                "query": request.message
            }

            # 3. 异步监听工作流事件 (使用 astream)
            # stream_mode="updates" 意味着每当一个节点跑完，我们就会收到通知
            async for event in workflow_manager.app.astream(inputs, stream_mode="updates"):
                
                # 情况 A: 聊天节点完成 (generate_answer) -> 立即推送给前端
                if "generate_answer" in event:
                    # 获取 AI 回复内容
                    # 注意：这里的数据结构取决于你的 workflow_nodes 返回值
                    # 假设返回的是 {"messages": [AIMessage(...)]}
                    ai_msg = event["generate_answer"]["messages"][-1]
                    content = ai_msg.content if hasattr(ai_msg, 'content') else str(ai_msg)
                    
                    # 构建数据包，使用 JSON 格式，末尾加换行符分隔
                    data = json.dumps({
                        "type": "answer",
                        "response": content,
                        "success": True
                    }, ensure_ascii=False)
                    yield f"{data}\n"
                
                # 情况 B: (可选) 只是为了调试，你可以推送后台状态
                # 前端可以选择忽略这些类型的信息
                if "kg_build" in event:
                    print(f"后台任务：知识图谱构建完成")
                
                if "save_memory" in event:
                    print(f"后台任务：记忆保存完成")

        # 返回流式响应，媒体类型设为 x-ndjson (Newline Delimited JSON)
        return StreamingResponse(event_stream(), media_type="application/x-ndjson")
        
    except Exception as e:
        print(f"API 错误: {e}")
        # 流式错误处理比较特殊，这里简单返回一个包含错误的 JSON
        return StreamingResponse(
            iter([json.dumps({"type": "error", "response": str(e)}, ensure_ascii=False) + "\n"]),
            media_type="application/x-ndjson"
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