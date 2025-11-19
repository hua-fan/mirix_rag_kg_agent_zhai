# -*- coding: utf-8 -*-
from typing import Dict, Any
from zhai_agent.models.chat_state import ChatState
from langchain_core.messages import HumanMessage


class UserInterface:
    """
    用户界面类，处理用户交互
    """
    
    def __init__(self):
        """
        初始化用户界面
        """
        self.welcome_message = "欢迎使用RAG增强的DeepSeek聊天机器人，请输入'exit'退出"
        self.rag_hint = "提示：请在documents目录中添加PDF或TXT文件以启用RAG功能"
    
    def display_welcome(self):
        """
        显示欢迎信息
        """
        print(self.welcome_message)
        print(self.rag_hint)
    
    def get_user_name(self):
        """
        获取用户姓名，用于区分不同用户的会话和记忆
        
        Returns:
            str: 用户姓名
        """
        user_name = input("请输入您的姓名（默认为'user_1'）: ")
        # 如果用户没有输入，使用默认值
        return user_name.strip() or "user_1"
    
    def get_user_input(self):
        """
        获取用户输入
        
        Returns:
            str: 用户输入的内容
        """
        return input("\n用户: ")
    
    def display_ai_response(self, result: Dict[str, Any]):
        """
        显示AI响应
        
        Args:
            result: 工作流执行结果
        """
        if result and 'messages' in result and result['messages']:
            last_message = result['messages'][-1]
            # 兼容字典和对象两种格式
            message_type = last_message.get('type') if isinstance(last_message, dict) else getattr(last_message, 'type', None)
            if message_type == "ai":
                message_content = last_message.get('content') if isinstance(last_message, dict) else getattr(last_message, 'content', '')
                print(f"\nAI: {message_content}")
            
            # 如果使用了RAG功能，询问是否显示检索的文档
            if result and 'retrieved_documents' in result and result['retrieved_documents']:
                self._display_retrieved_documents(result['retrieved_documents'])
    
    def _display_retrieved_documents(self, retrieved_documents: list):
        """
        显示检索到的文档
        
        Args:
            retrieved_documents: 检索到的文档列表
        """
        show_docs = input("\n是否显示检索到的参考文档？(y/n): ")
        if show_docs.lower() == 'y':
            print("\n=== 检索到的参考文档 ===")
            for i, doc in enumerate(retrieved_documents, 1):
                print(f"\n[文档 {i}]")
                # 控制显示的文档内容长度
                content_preview = doc['content'][:500] + '...' if len(doc['content']) > 500 else doc['content']
                print(content_preview)
                # 显示元数据
                if 'metadata' in doc and doc['metadata']:
                    print(f"来源: {doc['metadata'].get('source', '未知')}")
    
    def create_initial_state(self, user_input: str) -> ChatState:
        """
        创建初始聊天状态
        
        Args:
            user_input: 用户输入
            
        Returns:
            ChatState: 初始聊天状态
        """
        return ChatState(
            messages=[HumanMessage(content=user_input)],
            retrieved_documents=[],
            query=user_input
        )
    
    def handle_exit(self):
        """
        处理退出操作
        """
        print("再见！")