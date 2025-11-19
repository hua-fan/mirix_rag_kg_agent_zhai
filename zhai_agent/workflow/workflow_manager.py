# -*- coding: utf-8 -*-
from langgraph.graph.state import StateGraph
from typing import Dict, Any
from zhai_agent.models.chat_state import ChatState
from zhai_agent.rag.rag_manager import RAGManager
from zhai_agent.workflow.workflow_nodes import WorkflowNodes
from zhai_agent.mirix_memory.memory_agent import MirixMemoryAgent

class WorkflowManager:
    """
    工作流管理器，用于构建和运行LangGraph工作流
    职责：专注于工作流的构建和编译，具体节点逻辑委托给WorkflowNodes类
    """
    
    def __init__(self, retriever=None):
        """
        初始化工作流管理器
        Args:
            retriever: 文档检索器
        """
        self.retriever = retriever
        self.rag_manager = RAGManager()
        self.app = None
        # 创建自定义的MirixMemoryAgent实例，确保使用正确的配置
        custom_mirix_agent = MirixMemoryAgent()
        # 使用工作流节点类处理具体逻辑，并传入自定义的mirix_agent
        self.workflow_nodes = WorkflowNodes(self.rag_manager, retriever, mirix_agent=custom_mirix_agent)

    def get_mirix_memory_node(self,state:ChatState) -> Dict[str,Any]:
        """获取记忆节点"""
        return self.workflow_nodes.mirix_memory_node(state)

    def get_memory_node(self,state:ChatState) -> Dict[str,Any]:
        """获取记忆节点"""
        return self.workflow_nodes.normal_memory_node(state)

    def rag_node(self,state:ChatState) -> Dict[str,Any]:
        """
        RAG节点，用于从知识库提取相关文档
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        return self.workflow_nodes.rag_node(state)
    
    def chat_node(self, state: ChatState) -> Dict[str, Any]:
        """
        聊天节点，委托给WorkflowNodes处理
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        return self.workflow_nodes.chat_node(state)
    
    def llm_kg_node(self, state: ChatState) -> Dict[str, Any]:
        """
        智能聊天节点，支持LLM调用工具生成知识图谱
        委托给WorkflowNodes处理
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        return self.workflow_nodes.llm_kg_node(state)
    
    def store_memory_node(self, state: ChatState) -> Dict[str, Any]:
        """
        记忆存储节点，委托给WorkflowNodes处理
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        return self.workflow_nodes.store_memory_node(state)
    
    def kg_search_node(self, state: ChatState) -> Dict[str, Any]:
        """
        知识图谱搜索节点，委托给WorkflowNodes处理
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        return self.workflow_nodes.kg_search_node(state)

    def store_mirix_memory_node(self, state: ChatState) -> Dict[str, Any]:
        """
        记忆存储节点，委托给WorkflowNodes处理
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        return self.workflow_nodes.store_mirix_memory_node(state)
    
    def chat_node(self, state: ChatState) -> Dict[str, Any]:
        """
        纯聊天节点，委托给WorkflowNodes处理
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        return self.workflow_nodes.chat_node(state)
    
    def create_workflow(self):
        """
        创建工作流 - 分离知识图谱构建和聊天功能
        
        Returns:
            StateGraph: 创建的工作流
        """
        # Create state graph
        workflow = StateGraph(ChatState)
        
        # 添加节点 - 重新设计流程
        workflow.add_node("get_mirix_memory", self.get_mirix_memory_node)
        workflow.add_node("rag_node", self.rag_node)
        workflow.add_node("kg_search_node", self.kg_search_node)  # 知识图谱查询节点
        workflow.add_node("llm_kg_node", self.llm_kg_node)  # 知识图谱构建节点
        workflow.add_node("chat", self.chat_node)  # 纯聊天节点
        workflow.add_node("store_mirix_memory", self.store_mirix_memory_node)
        
        # 设置工作流流程 - 先构建知识图谱，再聊天
        workflow.set_entry_point("get_mirix_memory")
        workflow.add_edge("get_mirix_memory", "rag_node")
        workflow.add_edge("rag_node", "llm_kg_node")  # 先构建知识图谱
        workflow.add_edge("llm_kg_node", "kg_search_node")  # 构建完成后查询知识图谱
        workflow.add_edge("kg_search_node", "chat")  # 再进行正常聊天
        workflow.add_edge("chat", "store_mirix_memory")
        workflow.set_finish_point("store_mirix_memory")
        
        # 编译工作流
        self.app = workflow.compile()
        return self.app
    
    def process_user_request(self, user_message: str, user_name: str = "default_user", session_id: str = None) -> Dict[str, Any]:
        """
        处理用户请求，创建包含user_name的ChatState并运行工作流
        Args:
            user_message: 用户消息
            user_name: 用户姓名，用于记忆系统
            session_id: 会话ID，如果不提供则使用默认会话ID
        Returns:
            dict: 包含AI回复的结果
        """
        # 如果没有提供会话ID，使用默认值
        if session_id is None:
            session_id = "default_session"
        
        # 创建包含user_name和session_id的ChatState实例
        from langchain_core.messages import HumanMessage
        state = ChatState(
            messages=[HumanMessage(content=user_message)],
            user_name=user_name,
            session_id=session_id
        )
        
        # 确保工作流已编译
        if self.app is None:
            self.create_workflow()
        
        # 运行工作流
        result = self.app.invoke(state)
        
        return result
    
    def visualize_workflow(self, output_file="workflow_graph.png"):
        """
        可视化langgraph工作流
        Args:
            output_file: 输出文件名
        """
        try:
            if not self.app:
                print("工作流尚未创建，请先调用create_workflow方法")
                return
            
            # 生成工作流的Mermaid图表为PNG文件
            graph_image = self.app.get_graph().draw_mermaid_png()
            
            # 将图表保存到文件
            with open(output_file, "wb") as f:
                f.write(graph_image)
            
            print(f"\n工作流图表已保存为{output_file}")
            
            # 尝试在IPython环境中显示图表
            try:
                from IPython.display import Image, display
                display(Image(graph_image))
            except Exception:
                print("无法在当前环境中直接显示图表，但已成功保存")
        
        except Exception as e:
            print(f"生成工作流可视化时出错: {str(e)}")