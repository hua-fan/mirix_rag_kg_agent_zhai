# -*- coding: utf-8 -*-
"""
短期记忆管理模块
使用Redis存储和管理聊天历史和短期记忆
"""
import json
import redis
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime


class ShortMemory:
    """ 使用Redis实现的短期记忆存储管理器 """
    
    def __init__(self,
                 host: str = 'localhost',
                 port: int = 6379,
                 db: int = 0,
                 password: Optional[str] = None,
                 memory_ttl: int = 3600,
                 max_memory_size: int = 10):
        try:
            # 尝试连接Redis服务器
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True
            )
            # 测试连接
            self.redis_client.ping()
            self.is_connected = True
            print(f"成功连接到Redis服务器: {host}:{port} 数据库: {db}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            self.redis_client = None
            self.is_connected = False
            print(f"无法连接到Redis服务器: {str(e)}")
            print("将使用内存模式作为后备")
            # 创建内存中的临时存储作为后备
            self._memory_store = {}
        
        self.memory_ttl = memory_ttl
        self.max_memory_size = max_memory_size
        self.default_key_prefix = "chat_memory:"
    
    def _get_memory_key(self, user_id: str) -> str:
        """
        获取用户的内存键名
        Args:
            user_id: 用户标识符
        Returns:
            str: Redis键名
        """
        return f"{self.default_key_prefix}{user_id}"
    
    def store_memory(self, user_id: str, messages: List[Dict[str, Any]]) -> bool:
        """
        存储用户记忆到Redis
        
        Args:
            user_id: 用户标识符
            messages: 消息列表
        Returns:
            bool: 存储是否成功
        """
        try:
            # 序列化消息，确保包含所有必要字段
            serialized_messages = []
            for msg in messages[-self.max_memory_size:]:  # 每次只保留最新的消息
                # 确保消息是字典格式并包含所有必要字段
                if isinstance(msg, dict):
                    serialized_msg = {
                        "message_id": msg.get("message_id", str(uuid.uuid4())),
                        "type": msg.get("type", "human"),
                        "content": msg.get("content", ""),
                        "timestamp": msg.get("timestamp", datetime.now().isoformat()),
                        "additional_kwargs": msg.get("additional_kwargs", {}),
                        "name": msg.get("name", None),
                        "importance_score": msg.get("importance_score", 0.0)
                    }
                else:
                    # 尝试从对象获取属性
                    serialized_msg = {
                        "message_id": str(uuid.uuid4()),
                        "type": getattr(msg, "type", "human"),
                        "content": getattr(msg, "content", ""),
                        "timestamp": datetime.now().isoformat(),
                        "additional_kwargs": getattr(msg, "additional_kwargs", {}),
                        "name": getattr(msg, "name", None),
                        "importance_score": 0.0
                    }
                serialized_messages.append(serialized_msg)
            
            memory_data = json.dumps(serialized_messages, ensure_ascii=False)
            key = self._get_memory_key(user_id)
            
            if self.is_connected and self.redis_client:
                # 存储到Redis并设置过期时间
                self.redis_client.setex(key, self.memory_ttl, memory_data)
                print(f"成功将用户记忆存储到Redis: {user_id}")
            else:
                # 使用内存存储作为后备
                self._memory_store[key] = memory_data
                print(f"使用内存存储用户记忆: {user_id}")

            return True
        except Exception as e:
            print(f"存储记忆时出错: {str(e)}")
            return False
    
    def get_memory(self, user_id: str) -> List[Dict[str, Any]]:
        """
        从Redis获取用户记忆，确保返回的消息格式统一
        
        Args:
            user_id: 用户标识符
            
        Returns:
            List[Dict[str, Any]]: 记忆中的消息列表，每条消息都包含message_id、type、content、timestamp等必要字段
        """
        try:
            key = self._get_memory_key(user_id)
            memory_data = None
            
            if self.is_connected and self.redis_client:
                # 从Redis获取
                memory_data = self.redis_client.get(key)
            else:
                # 从内存存储获取
                memory_data = self._memory_store.get(key)
            
            if memory_data:
                messages = json.loads(memory_data)
                # 确保所有消息都包含必要字段
                normalized_messages = []
                for msg in messages:
                    normalized_msg = {
                        "message_id": msg.get("message_id", str(uuid.uuid4())),
                        "type": msg.get("type", "human"),
                        "content": msg.get("content", ""),
                        "timestamp": msg.get("timestamp", datetime.now().isoformat()),
                        "additional_kwargs": msg.get("additional_kwargs", {}),
                        "name": msg.get("name", None),
                        "importance_score": msg.get("importance_score", 0.0)
                    }
                    normalized_messages.append(normalized_msg)
                return normalized_messages
            return []
        except Exception as e:
            print(f"获取记忆时出错: {str(e)}")
            return []
    
    def add_message(self, user_id: str, message: Optional[Dict[str, Any]] = None, user_message: Optional[Dict[str, Any]] = None, **kwargs) -> bool:
        """
        向用户记忆添加一条消息，确保消息包含所有必要字段
        Args:
            user_id: 用户标识符
            message: 要添加的消息字典
            user_message: 备用参数名，用于兼容调用时使用user_message的情况
            **kwargs: 其他可能的参数，如importance_score
            
        Returns:
            bool: 添加是否成功
        """
        try:
            # 获取现有记忆
            existing_messages = self.get_memory(user_id)
            
            # 确定要使用的消息对象
            msg_to_use = message or user_message or {}
            
            # 获取重要性分数
            importance_score = kwargs.get("importance_score", 0.0)
            
            # 根据消息类型创建新消息（支持字典和对象），确保包含所有必要字段
            if isinstance(msg_to_use, dict):
                new_message = {
                    "message_id": msg_to_use.get("message_id", str(uuid.uuid4())),
                    "type": msg_to_use.get("type", "human"),
                    "content": msg_to_use.get("content", ""),
                    "timestamp": msg_to_use.get("timestamp", datetime.now().isoformat()),
                    "additional_kwargs": msg_to_use.get("additional_kwargs", {}),
                    "name": msg_to_use.get("name", None),
                    "importance_score": importance_score
                }
            else:
                # 尝试从对象获取属性
                new_message = {
                    "message_id": str(uuid.uuid4()),
                    "type": getattr(msg_to_use, "type", "human"),
                    "content": getattr(msg_to_use, "content", ""),
                    "timestamp": datetime.now().isoformat(),
                    "additional_kwargs": getattr(msg_to_use, "additional_kwargs", {}),
                    "name": getattr(msg_to_use, "name", None),
                    "importance_score": importance_score
                }
            existing_messages.append(new_message)
            
            # 限制消息数量上限
            if len(existing_messages) > self.max_memory_size:
                existing_messages = existing_messages[-self.max_memory_size:]
            
            # 重新存储
            key = self._get_memory_key(user_id)
            memory_data = json.dumps(existing_messages, ensure_ascii=False)
            
            if self.is_connected and self.redis_client:
                self.redis_client.setex(key, self.memory_ttl, memory_data)
            else:
                self._memory_store[key] = memory_data
            
            return True
        except Exception as e:
            print(f"添加消息到记忆时出错: {str(e)}")
            return False
    
    def delete_memory(self, user_id: str) -> bool:
        """
        删除指定用户的记忆
        Args:
            user_id: 用户标识符
            
        Returns:
            bool: 删除是否成功
        """
        try:
            key = self._get_memory_key(user_id)
            
            if self.is_connected and self.redis_client:
                self.redis_client.delete(key)
            else:
                if key in self._memory_store:
                    del self._memory_store[key]
            
            print(f"已删除用户记忆: {user_id}")
            return True
        except Exception as e:
            print(f"删除记忆时出错: {str(e)}")
            return False
    
    def list_users(self) -> List[str]:
        """
        列出所有当前存在的用户ID
        Returns:
            List[str]: 用户ID列表
        """
        try:
            sessions = []
            
            if self.is_connected and self.redis_client:
                # 使用Redis的SCAN命令查找所有匹配的键
                pattern = f"{self.default_key_prefix}*"
                for key in self.redis_client.scan_iter(match=pattern):
                    # 提取用户ID
                    user_id = key[len(self.default_key_prefix):]
                    sessions.append(user_id)
            else:
                # 从内存存储中获取
                for key in self._memory_store.keys():
                    if key.startswith(self.default_key_prefix):
                        user_id = key[len(self.default_key_prefix):]
                        sessions.append(user_id)
            
            return sessions
        except Exception as e:
            print(f"列出用户时出错: {str(e)}")
            return []
    
    def update_ttl(self, user_id: str, ttl: Optional[int] = None) -> bool:
        """
        更新用户记忆的过期时间
        
        Args:
            user_id: 用户标识符
            ttl: 新的过期时间（秒），如果为None则使用默认值
            
        Returns:
            bool: 更新是否成功
        """
        try:
            if not self.is_connected or not self.redis_client:
                # 内存模式下无法更新TTL
                return False
            
            key = self._get_memory_key(user_id)
            actual_ttl = ttl if ttl is not None else self.memory_ttl
            
            # 检查键是否存在
            if self.redis_client.exists(key):
                self.redis_client.expire(key, actual_ttl)
                return True
            return False
        except Exception as e:
            print(f"更新TTL时出错: {str(e)}")
            return False


# 导出默认实例
def get_shortmemory_instance(**kwargs) -> ShortMemory:
    """
    获取短期记忆的默认实例
    
    Args:
        **kwargs: 传递给ShortMemory构造函数的参数
        
    Returns:
        ShortMemory: 使用user_id进行用户区分的短期记忆管理器实例
    """
    return ShortMemory(**kwargs)