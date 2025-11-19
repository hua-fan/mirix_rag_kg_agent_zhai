# -*- coding: utf-8 -*-
from langgraph.graph.state import StateGraph
from langgraph.graph import END
from typing import Dict, Any
from zhai_agent.models.chat_state import ChatState
from zhai_agent.rag.rag_manager import RAGManager
from zhai_agent.workflow.workflow_nodes import WorkflowNodes
from zhai_agent.mirix_memory.memory_agent import MirixMemoryAgent

class WorkflowManager:
    """
    工作流管理器 - 优化版
    采用并行检索策略：(RAG + KG Search) -> Chat -> Save
    """
    
    def __init__(self, retriever=None):
        """
        初始化工作流管理器
        """
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

    # --- 节点包装方法 ---

    def get_mirix_memory_node(self, state: ChatState) -> Dict[str, Any]:
        """读取记忆节点"""
        return self.workflow_nodes.mirix_memory_node(state)

    def rag_node(self, state: ChatState) -> Dict[str, Any]:
        """RAG检索节点"""
        return self.workflow_nodes.rag_node(state)
    
    def kg_search_node(self, state: ChatState) -> Dict[str, Any]:
        """KG搜索节点"""
        return self.workflow_nodes.kg_search_node(state)
    
    def chat_node(self, state: ChatState) -> Dict[str, Any]:
        """聊天生成节点"""
        return self.workflow_nodes.chat_node(state)

    def store_mirix_memory_node(self, state: ChatState) -> Dict[str, Any]:
        """保存记忆节点"""
        return self.workflow_nodes.store_mirix_memory_node(state)
    
    def llm_kg_node(self, state: ChatState) -> Dict[str, Any]:
        """知识图谱构建节点"""
        return self.workflow_nodes.llm_kg_node(state)
    
    # --- 核心工作流构建 ---

    def create_workflow(self):
        """
        创建并行工作流
        流程: Start -> Load Memory -> (Parallel: RAG & KG Search) -> Chat -> Save Memory -> End
        """
        workflow = StateGraph(ChatState)
        
        # 1. 添加所有节点
        workflow.add_node("get_memory", self.get_mirix_memory_node)
        workflow.add_node("rag_search", self.rag_node)
        workflow.add_node("kg_search", self.kg_search_node)
        workflow.add_node("kg_build", self.llm_kg_node)      # 写图谱 (新增)
        workflow.add_node("generate_answer", self.chat_node)
        workflow.add_node("save_memory", self.store_mirix_memory_node)
        
        # 2. 定义边 (Edges)
        
        # 入口 -> 加载记忆
        workflow.set_entry_point("get_memory")
        
        # 加载记忆 -> 三路并行 (Fan-out)
        workflow.add_edge("get_memory", "rag_search")
        workflow.add_edge("get_memory", "kg_search")
        workflow.add_edge("get_memory", "kg_build")   # 同时开始构建
        
       # 三路汇聚 -> 生成回复 (Fan-in)
        # LangGraph 会等待这三个节点都执行完毕（或跳过）后，将状态合并传给 chat
        workflow.add_edge("rag_search", "generate_answer")
        workflow.add_edge("kg_search", "generate_answer")
        workflow.add_edge("kg_build", "generate_answer")
        
        # 生成回复 -> 保存记忆
        workflow.add_edge("generate_answer", "save_memory")
        
        # 保存记忆 -> 结束
        workflow.set_finish_point("save_memory")
        
        # 编译工作流
        self.app = workflow.compile()
        return self.app
    
    def process_user_request(self, user_message: str, user_name: str = "default_user", session_id: str = "default_session") -> Dict[str, Any]:
        """
        处理用户请求
        """
        from langchain_core.messages import HumanMessage
        
        # 初始化状态
        state = ChatState(
            messages=[HumanMessage(content=user_message)],
            user_name=user_name,
            session_id=session_id,
            query=user_message
        )
        
        if self.app is None:
            self.create_workflow()
        
        # 执行工作流
        try:
            result = self.app.invoke(state)
            return result
        except Exception as e:
            print(f"工作流执行出错: {e}")
            return {"error": str(e)}
    
    def visualize_workflow(self, output_file="workflow_graph.png"):
        """可视化工作流"""
        try:
            if not self.app:
                self.create_workflow()
            
            graph_image = self.app.get_graph().draw_mermaid_png()
            with open(output_file, "wb") as f:
                f.write(graph_image)
            print(f"工作流图表已保存为 {output_file}")
        except Exception as e:
            print(f"可视化失败 (可能是缺少依赖): {e}")