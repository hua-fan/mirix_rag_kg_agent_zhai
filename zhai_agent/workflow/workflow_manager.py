# -*- coding: utf-8 -*-
import logging
from langgraph.graph.state import StateGraph
from langgraph.graph import END
from typing import Dict, Any
from langchain_core.messages import HumanMessage 
import redis
from langgraph.checkpoint.redis import RedisSaver
from zhai_agent.models.chat_state import ChatState
from zhai_agent.rag.rag_manager import RAGManager
from zhai_agent.workflow.workflow_nodes import WorkflowNodes
from zhai_agent.mirix_memory.memory_agent import MirixMemoryAgent
from ..config import settings
logger = logging.getLogger(__name__)

class WorkflowManager:
    """
    工作流管理器 - 优化版
    流程：(RAG + KG Search) -> Chat -> (Save Memory + KG Build [后台运行])
    """
    
    def __init__(self, retriever=None):
        self.retriever = retriever
        self.rag_manager = RAGManager()
        self.app = None
        
        # 初始化记忆Agent
        custom_mirix_agent = MirixMemoryAgent()
        
        # 初始化节点逻辑处理类
        self.workflow_nodes = WorkflowNodes(
            self.rag_manager, 
            retriever, 
            mirix_agent=custom_mirix_agent
        )

        # 初始化 Checkpointer (连接 Redis)
        # 这里的参数需要匹配你的 Redis 配置
        self.redis_conn = redis.Redis(host=settings.REDIS_HOST,
                                       port=settings.REDIS_PORT,
                                       db= settings.REDIS_DB,
                                       password=settings.REDIS_PASSWORD)
        self.checkpointer = RedisSaver(self.redis_conn)

    # --- 节点包装方法 (保持不变) ---
    def get_mirix_memory_node(self, state: ChatState) -> Dict[str, Any]:
        return self.workflow_nodes.mirix_memory_node(state)

    def rag_node(self, state: ChatState) -> Dict[str, Any]:
        return self.workflow_nodes.rag_node(state)
    
    def kg_search_node(self, state: ChatState) -> Dict[str, Any]:
        return self.workflow_nodes.kg_search_node(state)
    
    def chat_node(self, state: ChatState) -> Dict[str, Any]:
        return self.workflow_nodes.chat_node(state)

    def store_mirix_memory_node(self, state: ChatState) -> Dict[str, Any]:
        return self.workflow_nodes.store_mirix_memory_node(state)
    
    def llm_kg_node(self, state: ChatState) -> Dict[str, Any]:
        return self.workflow_nodes.llm_kg_node(state)
    
    # --- 核心工作流构建 ---

    def create_workflow(self):
        """
        创建并行工作流
        优化后流程: 
        1. Start -> Load Memory
        2. Parallel -> (RAG & KG Search) [读操作]
        3. Merge -> Generate Answer [回复用户]
        4. Parallel -> (Save Memory & KG Build) [写操作，后台处理] -> End
        """
        workflow = StateGraph(ChatState)
        
        # 1. 添加所有节点
        workflow.add_node("get_memory", self.get_mirix_memory_node)
        workflow.add_node("rag_search", self.rag_node)
        workflow.add_node("kg_search", self.kg_search_node)
        workflow.add_node("generate_answer", self.chat_node)
        
        # 写操作节点
        workflow.add_node("kg_build", self.llm_kg_node)
        workflow.add_node("save_memory", self.store_mirix_memory_node)

        # 2. 定义边 (Edges)
        
        # 1. 设置唯一入口：先加载短期记忆
        # 这样确保 state["messages"] 最先被填充历史记录
        workflow.set_entry_point("get_memory")
        
        # 2. 长期记忆获取完毕 -> 开启并行检索 (RAG + KG)
        workflow.add_edge("get_memory", "rag_search")
        workflow.add_edge("get_memory", "kg_search")
        
        # 3. 检索汇聚 -> 生成回复
        workflow.add_edge("rag_search", "generate_answer")
        workflow.add_edge("kg_search", "generate_answer")
        
        # 4. 生成回复 -> 并行后台任务 (存记忆、建图谱)
        workflow.add_edge("generate_answer", "save_memory")
        workflow.add_edge("generate_answer", "kg_build")
        
        # 5. 结束
        workflow.add_edge("save_memory", END)
        workflow.add_edge("kg_build", END)
        
        self.app = workflow.compile()
        return self.app
     
    def process_user_request(self, user_message: str, user_name: str = "default_user", session_id: str = "default_session") -> Dict[str, Any]:
        """
        处理用户请求
        """
        if self.app is None:
            self.create_workflow()
        
        config = {"configurable": {"thread_id": session_id}}
    
        inputs = {
            "messages": [HumanMessage(content=user_message)], 
            "user_name": user_name,
            "query": user_message
        }
        
        # 执行工作流
        try:
            # invoke 接受字典作为输入
            result = self.app.invoke(inputs,config=config)
            return result
        except Exception as e:
            logger.error(f"工作流执行出错: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
    
    def visualize_workflow(self, output_file="workflow_graph.png"):
        """可视化工作流"""
        try:
            if not self.app:
                self.create_workflow()
            
            graph_image = self.app.get_graph().draw_mermaid_png()
            with open(output_file, "wb") as f:
                f.write(graph_image)
            logger.info(f"工作流图表已保存为 {output_file}")
        except Exception as e:
            logger.error(f"可视化失败 (可能是缺少依赖): {e}")