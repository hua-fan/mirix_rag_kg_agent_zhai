# -*- coding: utf-8 -*-
import logging
import os
from langchain_community.document_loaders import TextLoader, PyPDFLoader

logger = logging.getLogger(__name__)


class DocumentLoader:
    """
    文档加载器类，负责从指定目录加载文档
    """
    
    def __init__(self, documents_dir="documents"):
        """
        初始化文档加载器
        
        Args:
            documents_dir: 文档目录路径
        """
        self.documents_dir = documents_dir
        # 确保文档目录存在
        os.makedirs(self.documents_dir, exist_ok=True)
    
    def load_documents(self):
        """
        从documents目录加载所有文档
        
        Returns:
            list: 加载的文档列表
        """
        documents = []
        
        # 检查documents目录是否存在
        if not os.path.exists(self.documents_dir):
            return documents
        
        # 遍历documents目录中的所有文件
        for filename in os.listdir(self.documents_dir):
            file_path = os.path.join(self.documents_dir, filename)
            
            try:
                if filename.endswith('.pdf'):
                    loader = PyPDFLoader(file_path)
                    docs = loader.load()
                    documents.extend(docs)
                elif filename.endswith('.txt'):
                    loader = TextLoader(file_path, encoding='utf-8')
                    docs = loader.load()
                    documents.extend(docs)
                logger.info(f"已加载文件: {filename}")
            except Exception as e:
                logger.error(f"加载文件 {filename} 时出错: {str(e)}")
        
        return documents