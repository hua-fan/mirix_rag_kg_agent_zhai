# -*- coding: utf-8 -*-
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.embeddings import FakeEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain.schema import Document
import os
import requests
# 尝试导入sentence_transformers，但不强制要求
SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """
    向量存储管理器，负责创建和管理向量存储
    """
    
    def __init__(self):
        """
        初始化向量存储管理器
        """
        self.vectorstore = None
        self.retriever = None
    
    def create_vectorstore(self, documents):
        """
        为文档创建向量存储
        Args:
            documents: 文档列表
            
        Returns:
            FAISS: 向量存储实例
        """
        if not documents:
            return None
        
        # 将文档分割成块
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        chunks = text_splitter.split_documents(documents)
        
        logger.info(f"文档已分割为 {len(chunks)} 块")
        
        # 嵌入模型 - 使用轻量级模型
        # 首先检查是否已有缓存的模型文件
        model_cache_path = os.path.join("./models_cache", "sentence-transformers_all-MiniLM-L6-v2")
        
        # 设置环境变量
        os.environ['TRANSFORMERS_OFFLINE'] = '0'
        os.environ['HF_HUB_OFFLINE'] = '0'
        
        # 创建缓存目录（如果不存在）
        if not os.path.exists("./models_cache"):
            os.makedirs("./models_cache")
        
        # 定义一个简单的检查函数来测试网络连接
        def check_huggingface_connection():
            try:
                logger.info("检查与huggingface.co的网络连接...")
                # 使用较短的超时时间快速检查
                response = requests.head("https://hf-mirror.com", timeout=5)
                logger.info("成功连接到huggingface.co")
                return True
            except requests.RequestException:
                logger.warning("无法连接到huggingface.co，可能存在网络限制")
                return False
        
        # 首先尝试使用假嵌入模型（最可靠的方式）
        logger.info("考虑到网络连接限制，优先使用假嵌入模型以确保程序正常运行")
        embeddings = FakeEmbeddings(size=384)
        logger.info("已初始化假嵌入模型")
        
        # 仅在有网络连接时尝试加载真实模型
        if check_huggingface_connection():
            logger.info("尝试加载HuggingFace嵌入模型...")
            try:
                # 先尝试直接使用LangChain的HuggingFaceEmbeddings
                embeddings = HuggingFaceEmbeddings(
                    model_name="all-MiniLM-L6-v2",
                    model_kwargs={'device': 'cpu'},
                    cache_folder="./models_cache"
                )
                logger.info("成功加载HuggingFace嵌入模型")
            except Exception as e:
                logger.error(f"加载HuggingFace模型时出错: {str(e)}")
                logger.info("继续使用假嵌入模型")
        else:
            logger.warning("由于网络限制，将继续使用假嵌入模型")
            logger.info("提示：在实际生产环境中，建议预先下载模型并配置离线使用")
            logger.info("或考虑使用本地托管的嵌入服务")
        
        # 创建向量存储
        vectorstore = FAISS.from_documents(chunks, embeddings)
        self.vectorstore = vectorstore
        return vectorstore
    
    def setup_retriever(self, vectorstore, k=3):
        """
        设置混合检索器，结合向量检索和BM25关键词检索
        Args:
            vectorstore: 向量存储实例
            k: 混合检索的总文档数量
        Returns:
            EnsembleRetriever: 混合检索器实例
        """
        if vectorstore:
            # 获取向量存储中的所有文档
            all_docs = vectorstore.docstore._dict.values()
            docs_list = list(all_docs) if isinstance(all_docs, dict) else list(all_docs)
            # 创建向量检索器
            vector_retriever = vectorstore.as_retriever(search_kwargs={"k": k})
            logger.info("已创建向量检索器")
            # 创建BM25检索器
            bm25_retriever = BM25Retriever.from_documents(docs_list)
            bm25_retriever.k = k  # 设置BM25检索的文档数量
            logger.info("已创建BM25关键词检索器")
            # 创建混合检索器，权重可以根据需要调整
            ensemble_retriever = EnsembleRetriever(
                retrievers=[vector_retriever, bm25_retriever],
                weights=[0.7, 0.3]  # 向量检索权重0.7，BM25权重0.3
            )
            logger.info("已创建混合检索器，结合向量检索和BM25关键词检索")

            self.retriever = ensemble_retriever
            return ensemble_retriever
        
        # 如果没有向量存储，返回None
        return None