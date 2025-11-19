# -*- coding: utf-8 -*-
from typing import List
from langchain_core.documents import Document
from langchain_community.cross_encoders import HuggingFaceCrossEncoder


class DocumentReranker:
    """
    文档重排器，负责对检索到的文档进行相关性重排
    """
    
    def __init__(self, model_name="BAAI/bge-reranker-base"):
        """
        初始化文档重排器
        Args:
            model_name: 重排模型名称
        """
        self.model_name = model_name
        self.rerank_model = None
        self._load_model()
    
    def _load_model(self):
        """
        加载重排模型
        """
        try:
            self.rerank_model = HuggingFaceCrossEncoder(model_name=self.model_name)
            print(f"{self.model_name} 重排模型加载成功")
        except Exception as e:
            print(f"加载重排模型时出错: {str(e)}")
            self.rerank_model = None
    
    def rerank_documents(self, retrieved_docs: List[Document], query: str) -> List[Document]:
        """
        对检索到的文档进行重新排序
        Args:
            retrieved_docs: 检索到的文档列表
            query: 用户查询
        Returns:
            List[Document]: 重新排序后的文档列表
        """
        # 如果没有文档或模型未加载，直接返回原始文档
        if not retrieved_docs or not self.rerank_model:
            return retrieved_docs
        
        try:
            # 准备查询-文档对
            pairs = [[query, doc.page_content] for doc in retrieved_docs]
            
            # 获取相关性分数
            scores = self.rerank_model.predict(pairs)
            
            # 按分数降序排序文档
            sorted_docs = [doc for _, doc in sorted(zip(scores, retrieved_docs), 
                                                  key=lambda x: x[0], reverse=True)]
            
            # 记录重排结果
            print(f"文档重排完成，共 {len(sorted_docs)} 个文档")
            if sorted_docs:
                # 打印前几个文档的相关性分数（为了调试）
                print(f"前 {min(3, len(sorted_docs))} 个最相关文档已排序")
            
            return sorted_docs
            
        except Exception as e:
            print(f"重新排序文档时出错: {str(e)}")
            # 出错时返回原始文档
            return retrieved_docs
    
    def rerank_with_scores(self, retrieved_docs: List[Document], query: str) -> List[tuple]:
        """
        对检索到的文档进行重新排序并返回分数
        Args:
            retrieved_docs: 检索到的文档列表
            query: 用户查询
        Returns:
            List[tuple]: 包含(文档, 分数)的列表
        """
        if not retrieved_docs or not self.rerank_model:
            return [(doc, 0.0) for doc in retrieved_docs]
        
        try:
            pairs = [[query, doc.page_content] for doc in retrieved_docs]
            scores = self.rerank_model.predict(pairs)
            
            # 返回文档和分数的元组列表，按分数降序排序
            scored_docs = sorted(zip(retrieved_docs, scores), key=lambda x: x[1], reverse=True)
            return scored_docs
            
        except Exception as e:
            print(f"重新排序文档时出错: {str(e)}")
            return [(doc, 0.0) for doc in retrieved_docs]


def get_document_reranker(model_name="BAAI/bge-reranker-base"):
    """
    获取文档重排器实例
    Args:
        model_name: 重排模型名称
    Returns:
        DocumentReranker: 文档重排器实例
    """
    return DocumentReranker(model_name)