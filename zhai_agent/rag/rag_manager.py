# -*- coding: utf-8 -*-
import logging
import os
from typing import List
from langchain_core.documents import Document
from ..llm.llm_client import get_llm_client
from ..rag.document_reranker import get_document_reranker
from ..config import settings
from ..prompt.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class RAGManager:
    """
    RAG管理器，协调文档检索、重排、提示构建和模型调用等组件
    """
    
    def __init__(self):
        """
        初始化RAG管理器，加载各个组件
        """
        if not os.getenv("DEEPSEEK_API_KEY") and settings.DEEPSEEK_API_KEY:
             os.environ["DEEPSEEK_API_KEY"] = settings.DEEPSEEK_API_KEY
        # 初始化各个组件
        self.llm_client = get_llm_client()
        self.document_reranker = get_document_reranker()
        self.prompt_builder = PromptBuilder()
    
    def retrieve_documents(self, retriever, query):
        """
        使用检索器检索相关文档
        
        Args:
            retriever: 文档检索器
            query: 用户查询
            
        Returns:
            list: 检索到的文档列表
        """
        if not retriever:
            return []
        
        try:
            retrieved_docs = retriever.invoke(query)
            return retrieved_docs
        except Exception as e:
            logger.error(f"检索文档时出错: {str(e)}")
            return []
    
    def reRank(self, retrieved_docs: List[Document], query: str) -> List[Document]:
        """
        对检索到的文档进行重新排序
        
        Args:
            retrieved_docs: 检索到的文档列表
            query: 用户查询
        Returns:
            List[Document]: 重新排序后的文档列表
        """
        return self.document_reranker.rerank_documents(retrieved_docs, query)
    
    def format_retrieved_documents(self, retrieved_docs: List[Document]) -> str:
        """
        格式化检索到的文档
        
        Args:
            retrieved_docs: 检索到的文档列表
            
        Returns:
            str: 格式化后的文档字符串
        """
        return self.prompt_builder.format_retrieved_documents(retrieved_docs)

    
    def build_prompt(self, retrieved_docs: List[Document], query: str, 
                    conversation_history: str = "") -> str:
        """
        构建RAG提示
        
        Args:
            retrieved_docs: 检索到的文档列表
            query: 用户查询
            conversation_history: 对话历史（可选）
            
        Returns:
            str: 构建的提示
        """
        return self.prompt_builder.build_rag_prompt(
            retrieved_docs, query, conversation_history
        )

    
    def call_llm(self, prompt: str) -> str:
        """
        调用语言模型
        
        Args:
            prompt: 提示内容
            
        Returns:
            str: 模型响应
        """
        return self.llm_client.call_model(prompt)

    