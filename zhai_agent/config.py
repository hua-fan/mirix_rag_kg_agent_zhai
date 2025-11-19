# zhai_agent/config.py
import os
import logging
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    # --- LLM 配置 ---
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")
    
    # --- Mirix (Gemini) 配置 ---
    MIRIX_API_KEY = os.getenv("MIRIX_API_KEY", "")
    MIRIX_MODEL_NAME = os.getenv("MIRIX_MODEL_NAME", "gemini-2.5-flash")

    # --- Neo4j 知识图谱配置 ---
    NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "huafan123") # 建议修改默认密码

    # --- PostgreSQL 长期记忆配置 ---
    PG_HOST = os.getenv("PG_HOST", "localhost")
    PG_PORT = int(os.getenv("PG_PORT", 5432))
    PG_DATABASE = os.getenv("PG_DATABASE", "zhai_agent")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD", "huafan123") # 建议修改默认密码

    # --- Redis 短期记忆配置 ---
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
    
    # --- RAG 配置 ---
    RAG_MODEL_NAME = os.getenv("RAG_MODEL_NAME", "BAAI/bge-reranker-base")

# 实例化供其他模块使用
settings = Config()