# -*- coding: utf-8 -*-
"""
Zhai Agent 主模块
"""

import logging
from zhai_agent.document_processor.document_loader import DocumentLoader
from zhai_agent.vector_store.vector_store_manager import VectorStoreManager
from zhai_agent.workflow.workflow_manager import WorkflowManager
from zhai_agent.ui.user_interface import UserInterface

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def setup_rag_system():
    """
    设置RAG系统的各个组件
    
    Returns:
        tuple: (workflow_manager, user_interface)
    """
    logger.info("开始设置RAG系统...")
    
    # 1. 加载文档
    logger.info("正在加载文档...")
    document_loader = DocumentLoader()
    documents = document_loader.load_documents()
    logger.info(f"成功加载 {len(documents)} 个文档")
    
    # 2. 创建向量存储和检索器
    logger.info("正在创建向量存储和检索器...")
    vector_store_manager = VectorStoreManager()
    vectorstore = None
    retriever = None
    
    if documents:
        vectorstore = vector_store_manager.create_vectorstore(documents)
        retriever = vector_store_manager.setup_retriever(vectorstore)
        logger.info("向量存储和检索器创建成功")
    else:
        logger.info("没有找到文档，请在documents目录中添加PDF或TXT文件")
    
    # 3. 创建工作流管理器
    logger.info("正在创建工作流管理器...")
    workflow_manager = WorkflowManager(retriever)
    workflow_manager.create_workflow()
    logger.info("工作流管理器创建成功")
    
    # 4. 创建用户界面
    logger.info("正在创建用户界面...")
    user_interface = UserInterface()
    logger.info("用户界面创建成功")
    
    logger.info("RAG系统设置完成")
    return workflow_manager, user_interface


def run_chatbot():
    """
    运行聊天机器人
    """
    logger.info("开始运行聊天机器人...")
    
    # 设置RAG系统
    workflow_manager, user_interface = setup_rag_system()
    
    # 可视化工作流
    logger.info("正在可视化工作流...")
    workflow_manager.visualize_workflow()
    
    # 显示欢迎信息
    user_interface.display_welcome()
    
    # 获取用户姓名
    user_name = user_interface.get_user_name()
    logger.info(f"用户名称: {user_name}")
    
    # 主循环
    logger.info("进入主循环，等待用户输入...")
    while True:
        # 获取用户输入
        user_input = user_interface.get_user_input()
        
        if user_input.lower() == 'exit':
            logger.info("用户选择退出程序")
            user_interface.handle_exit()
            break
        
        logger.info(f"收到用户输入: {user_input[:50]}...")
        
        # 使用process_user_request方法处理请求
        result = workflow_manager.process_user_request(
            user_message=user_input,
            user_name=user_name
        )
        
        # 显示AI响应
        user_interface.display_ai_response(result)
        logger.info("AI响应已显示")


if __name__ == "__main__":
    logger.info("Zhai Agent 启动中...")
    try:
        run_chatbot()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}")
    finally:
        logger.info("Zhai Agent 已关闭")