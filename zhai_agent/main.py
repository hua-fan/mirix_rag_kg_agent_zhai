# -*- coding: utf-8 -*-
"""
Zhai Agent 主模块
"""

from zhai_agent.document_processor.document_loader import DocumentLoader
from zhai_agent.vector_store.vector_store_manager import VectorStoreManager
from zhai_agent.workflow.workflow_manager import WorkflowManager
from zhai_agent.ui.user_interface import UserInterface


def setup_rag_system():
    """
    设置RAG系统的各个组件
    
    Returns:
        tuple: (workflow_manager, user_interface)
    """
    # 1. 加载文档
    document_loader = DocumentLoader()
    documents = document_loader.load_documents()
    
    # 2. 创建向量存储和检索器
    vector_store_manager = VectorStoreManager()
    vectorstore = None
    retriever = None
    
    if documents:
        vectorstore = vector_store_manager.create_vectorstore(documents)
        retriever = vector_store_manager.setup_retriever(vectorstore)
    else:
        print("没有找到文档，请在documents目录中添加PDF或TXT文件")
    
    # 3. 创建工作流管理器
    workflow_manager = WorkflowManager(retriever)
    workflow_manager.create_workflow()
    
    # 4. 创建用户界面
    user_interface = UserInterface()
    
    return workflow_manager, user_interface


def run_chatbot():
    """
    运行聊天机器人
    """
    # 设置RAG系统
    workflow_manager, user_interface = setup_rag_system()
    
    # 可视化工作流
    workflow_manager.visualize_workflow()
    
    # 显示欢迎信息
    user_interface.display_welcome()
    
    # 获取用户姓名
    user_name = user_interface.get_user_name()
    
    # 主循环
    while True:
        # 获取用户输入
        user_input = user_interface.get_user_input()
        
        if user_input.lower() == 'exit':
            user_interface.handle_exit()
            break
        
        # 使用process_user_request方法处理请求
        result = workflow_manager.process_user_request(
            user_message=user_input,
            user_name=user_name
        )
        
        # 显示AI响应
        user_interface.display_ai_response(result)


if __name__ == "__main__":
    run_chatbot()