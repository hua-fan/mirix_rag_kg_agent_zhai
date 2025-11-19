# -*- coding: utf-8 -*-
"""
长期记忆管理模块
使用PostgreSQL存储和管理长期对话记忆
"""
import psycopg2
from psycopg2.extras import DictCursor
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..config import settings

logger = logging.getLogger(__name__)

class LongMemory:
    """ 使用PostgreSQL实现的长期记忆存储管理器 """
    
    def __init__(self,
                 host: str = None,
                 port: int = None,
                 database: str = None,
                 user: str = None,
                 password: str = None):
        """
        初始化长期记忆管理器
        
        Args:
            host: PostgreSQL主机地址
            port: PostgreSQL端口号
            database: 数据库名称
            user: 数据库用户名
            password: 数据库密码
        """
        self.host = host or settings.PG_HOST
        self.port = port or settings.PG_PORT
        self.database = database or settings.PG_DATABASE
        self.user = user or settings.PG_USER
        self.password = password or settings.PG_PASSWORD
        try:
            # 尝试连接PostgreSQL数据库
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            self.cursor = self.conn.cursor(cursor_factory=DictCursor)
            self.is_connected = True
            logger.info(f"成功连接到PostgreSQL服务器: {host}:{port} 数据库: {database}")
            
            # 创建表结构（如果不存在）
            self._create_tables()
            
        except psycopg2.OperationalError as e:
            self.conn = None
            self.cursor = None
            self.is_connected = False
            logger.error(f"无法连接到PostgreSQL服务器: {str(e)}")
            logger.warning("长期记忆功能将不可用")
    
    def _create_tables(self):
        """
        创建必要的数据库表结构
        """
        if not self.is_connected:
            return
            
        try:
            # 创建会话表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_ids (
                    user_id VARCHAR(255) PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建记忆表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS long_term_memory (
                    id SERIAL PRIMARY KEY,
                    message_id VARCHAR(255) NOT NULL,  -- 统一的消息ID
                    user_id VARCHAR(255) REFERENCES user_ids(user_id),
                    message_type VARCHAR(50) NOT NULL,  -- 'human' 或 'ai'
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    importance_score FLOAT DEFAULT 0.0  -- 用于标记重要性
                )
            ''')
            
            # 创建索引以提高查询性能
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_memory_user_id 
                ON long_term_memory(user_id)
            ''')
            
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_memory_created_at 
                ON long_term_memory(created_at)
            ''')
            
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_memory_importance 
                ON long_term_memory(importance_score DESC)
            ''')
            
            # 添加message_id索引
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_memory_message_id 
                ON long_term_memory(message_id)
            ''')
            
            self.conn.commit()
            logger.info("数据库表结构创建成功")
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"创建数据库表结构时出错: {str(e)}")
    
    def _ensure_user_exists(self, user_id: str):
        """
        确保用户记录存在
        
        Args:
            user_id: 用户标识符
        """
        if not self.is_connected:
            return
            
        try:
            # 检查表是否存在，如果不存在则创建
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_ids (
                    user_id VARCHAR(255) PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 检查用户是否存在
            self.cursor.execute(
                "SELECT user_id FROM user_ids WHERE user_id = %s",
                (user_id,)
            )
            
            if not self.cursor.fetchone():
                # 用户不存在，创建新用户
                self.cursor.execute(
                    "INSERT INTO user_ids (user_id) VALUES (%s)",
                    (user_id,)
                )
            else:
                # 更新用户的最后更新时间
                self.cursor.execute(
                    "UPDATE user_ids SET last_updated = CURRENT_TIMESTAMP WHERE user_id = %s",
                    (user_id,)
                )
            
            self.conn.commit()
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"确保用户存在时出错: {str(e)}")
    
    def store_memory(self, user_id: str, messages: List[Dict[str, Any]], importance_score: float = 0.0):
        """
        存储长期记忆到PostgreSQL，确保包含所有必要字段
        
        Args:
            user_id: 用户标识符
            messages: 消息列表
            importance_score: 重要性分数，默认为0.0
            
        Returns:
            bool: 存储是否成功
        """
        if not self.is_connected:
            return False
            
        try:
            # 确保用户存在
            self._ensure_user_exists(user_id)
            
            # 存储消息
            for msg in messages:
                # 确保消息是字典格式并包含所有必要字段
                if isinstance(msg, dict):
                    message_type = msg.get("type", "human")
                    content = msg.get("content", "")
                    message_id = msg.get("message_id", str(uuid.uuid4()))
                    timestamp = msg.get("timestamp", datetime.now().isoformat())
                    # 使用消息中指定的重要性分数，如果没有则使用默认值
                    msg_importance_score = msg.get("importance_score", importance_score)
                    metadata = {
                        "additional_kwargs": msg.get("additional_kwargs", {}),
                        "name": msg.get("name", None),
                        "timestamp": timestamp  # 存储timestamp到metadata中
                    }
                else:
                    # 尝试从对象获取属性
                    message_type = getattr(msg, "type", "human")
                    content = getattr(msg, "content", "")
                    message_id = str(uuid.uuid4())
                    timestamp = datetime.now().isoformat()
                    msg_importance_score = importance_score
                    metadata = {
                        "additional_kwargs": getattr(msg, "additional_kwargs", {}),
                        "name": getattr(msg, "name", None),
                        "timestamp": timestamp
                    }
                
                # 插入记忆
                self.cursor.execute('''
                    INSERT INTO long_term_memory 
                    (user_id, message_id, message_type, content, metadata, importance_score) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (user_id, message_id, message_type, content, json.dumps(metadata), msg_importance_score))
            
            self.conn.commit()
            logger.info(f"成功将用户记忆存储到PostgreSQL: {user_id}")
            return True
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"存储长期记忆时出错: {str(e)}")
            return False
    
    def add_message(self, user_id: str, message: Dict[str, Any], importance_score: float = 0.0):
        """
        添加单条消息到长期记忆
        
        Args:
            user_id: 用户标识符
            message: 消息字典
            importance_score: 重要性分数，默认为0.0
            
        Returns:
            bool: 添加是否成功
        """
        return self.store_memory(user_id, [message], importance_score)
    
    def get_memory(self, user_id: str, limit: int = 100, order_by: str = 'created_at'):
        """
        获取用户的长期记忆，确保返回的消息格式统一
        
        Args:
            user_id: 用户标识符
            limit: 返回的最大消息数量
            order_by: 排序方式，可选 'created_at'（按时间）或 'importance_score'（按重要性）
            
        Returns:
            List[Dict]: 记忆列表，每条消息都包含message_id、type、content、timestamp等必要字段
        """
        if not self.is_connected:
            return []
            
        try:
            # 验证排序参数
            if order_by not in ['created_at', 'importance_score']:
                order_by = 'created_at'
            
            # 构建查询
            query = f'''
                SELECT * FROM long_term_memory 
                WHERE user_id = %s 
                ORDER BY {order_by} DESC 
                LIMIT %s
            '''
            
            self.cursor.execute(query, (user_id, limit))
            rows = self.cursor.fetchall()
            
            # 转换为字典列表，确保包含所有必要字段
            memories = []
            for row in rows:
                # 从metadata中获取timestamp，如果没有则使用数据库中的created_at
                metadata_timestamp = row['metadata'].get('timestamp') if isinstance(row['metadata'], dict) else None
                timestamp = metadata_timestamp if metadata_timestamp else (row['created_at'].isoformat() if row['created_at'] else datetime.now().isoformat())
                
                memory = {
                    'message_id': row.get('message_id', str(uuid.uuid4())),  # 确保有message_id
                    'type': row['message_type'],
                    'content': row['content'],
                    'timestamp': timestamp,
                    'additional_kwargs': row['metadata'].get('additional_kwargs', {}) if isinstance(row['metadata'], dict) else {},
                    'name': row['metadata'].get('name', None) if isinstance(row['metadata'], dict) else None,
                    'importance_score': row['importance_score']
                }
                memories.append(memory)
            
            # 如果按时间排序，反转列表使其按时间正序返回
            if order_by == 'created_at':
                memories.reverse()
            
            return memories
            
        except Exception as e:
            logger.error(f"获取长期记忆时出错: {str(e)}")
            return []
    
    def search_memory(self, user_id: str, query: str, limit: int = 20):
        """
        基于内容搜索长期记忆，确保返回的消息格式统一
        
        Args:
            user_id: 用户标识符
            query: 搜索关键词
            limit: 返回的最大结果数量
            
        Returns:
            List[Dict]: 匹配的记忆列表，每条消息都包含message_id、type、content、timestamp等必要字段
        """
        if not self.is_connected:
            return []
            
        try:
            # 使用PostgreSQL的全文搜索功能
            self.cursor.execute('''
                SELECT * FROM long_term_memory 
                WHERE user_id = %s 
                AND content ILIKE %s 
                ORDER BY created_at DESC 
                LIMIT %s
            ''', (user_id, f'%{query}%', limit))
            
            rows = self.cursor.fetchall()
            
            # 转换为字典列表，确保包含所有必要字段
            memories = []
            for row in rows:
                # 从metadata中获取timestamp，如果没有则使用数据库中的created_at
                metadata_timestamp = row['metadata'].get('timestamp') if isinstance(row['metadata'], dict) else None
                timestamp = metadata_timestamp if metadata_timestamp else (row['created_at'].isoformat() if row['created_at'] else datetime.now().isoformat())
                
                memory = {
                    'message_id': row.get('message_id', str(uuid.uuid4())),  # 确保有message_id
                    'type': row['message_type'],
                    'content': row['content'],
                    'timestamp': timestamp,
                    'additional_kwargs': row['metadata'].get('additional_kwargs', {}) if isinstance(row['metadata'], dict) else {},
                    'name': row['metadata'].get('name', None) if isinstance(row['metadata'], dict) else None,
                    'importance_score': row['importance_score']
                }
                memories.append(memory)
            
            return memories
            
        except Exception as e:
            logger.error(f"搜索长期记忆时出错: {str(e)}")
            return []
    
    def update_importance(self, memory_id: int, importance_score: float):
        """
        更新记忆的重要性分数
        
        Args:
            memory_id: 记忆ID
            importance_score: 新的重要性分数
            
        Returns:
            bool: 更新是否成功
        """
        if not self.is_connected:
            return False
            
        try:
            self.cursor.execute(
                "UPDATE long_term_memory SET importance_score = %s WHERE id = %s",
                (importance_score, memory_id)
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"更新记忆重要性时出错: {str(e)}")
            return False
    
    def delete_memory(self, user_id: str, memory_id: int = None):
        """
        删除长期记忆
        
        Args:
            user_id: 用户标识符
            memory_id: 可选的记忆ID，不提供则删除整个用户的记忆
            
        Returns:
            bool: 删除是否成功
        """
        if not self.is_connected:
            return False
            
        try:
            if memory_id:
                # 删除特定记忆
                self.cursor.execute(
                    "DELETE FROM long_term_memory WHERE user_id = %s AND id = %s",
                    (user_id, memory_id)
                )
            else:
                # 删除整个用户的记忆
                self.cursor.execute(
                    "DELETE FROM long_term_memory WHERE user_id = %s",
                    (user_id,)
                )
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"删除长期记忆时出错: {str(e)}")
            return False
    
    def list_users(self):
        """
        列出所有存在的用户ID
        
        Returns:
            List[str]: 用户ID列表
        """
        if not self.is_connected:
            return []
            
        try:
            self.cursor.execute(
                "SELECT user_id FROM user_ids ORDER BY last_updated DESC"
            )
            rows = self.cursor.fetchall()
            return [row['user_id'] for row in rows]
            
        except Exception as e:
            logger.error(f"列出用户时出错: {str(e)}")
            return []
    
    def close(self):
        """
        关闭数据库连接
        """
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        self.is_connected = False
        logger.info("PostgreSQL连接已关闭")


# 全局实例管理
def get_longmemory_instance(**kwargs):
    if not hasattr(get_longmemory_instance, '_instance'):
        # 参数将由 __init__ 中的逻辑处理，自动回退到 settings
        get_longmemory_instance._instance = LongMemory(**kwargs)
    return get_longmemory_instance._instance
