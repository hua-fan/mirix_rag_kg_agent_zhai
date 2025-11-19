# -*- coding: utf-8 -*-
"""
MCP上下文管理器模块
提供会话上下文管理功能，使用MemoryManager处理记忆操作
"""
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from datetime import datetime
import uuid
from config import settings
from zhai_agent.memory.shortmemory import ShortMemory
from zhai_agent.memory.longmemory import get_longmemory_instance
from zhai_agent.memory.memory_manager import MemoryManager, ShortTermMemoryBackend, LongTermMemoryBackend


class MCPContextManager:
    """
    MCP上下文管理器
    统一管理短期记忆和长期记忆，提供会话上下文的完整生命周期管理
    """
    
    def __init__(self, 
                 user_id: str,
                 redis_host: str = 'localhost',
                 redis_port: int = 6379,
                 redis_db: int = 0,
                 redis_password: Optional[str] = None,
                 pg_host: str = 'localhost',
                 pg_port: int = 5432,
                 pg_database: str = None,
                 pg_user: str = None,
                 pg_password: str = None,
                 short_memory_ttl: int = 3600,
                 short_memory_max_size: int = 10,
                 long_memory_importance_threshold: float = 0.5):
        self.user_id = user_id
        # 初始化具体记忆实例
        short_memory_instance = ShortMemory(
            host=redis_host or settings.REDIS_HOST,
            port=redis_port or settings.REDIS_PORT,
            db=redis_db or settings.REDIS_DB,
            password=redis_password or settings.REDIS_PASSWORD,
            memory_ttl=short_memory_ttl,
            max_memory_size=short_memory_max_size
        )
        
        long_memory_instance = get_longmemory_instance(
            host=pg_host or settings.POSTGRES_HOST,
            port=pg_port or settings.POSTGRES_PORT,
            database=pg_database or settings.POSTGRES_DATABASE,
            user=pg_user or settings.POSTGRES_USER,
            password=pg_password or settings.POSTGRES_PASSWORD
        )
        
        # 创建记忆后端
        short_memory_backend = ShortTermMemoryBackend(short_memory_instance)
        long_memory_backend = LongTermMemoryBackend(long_memory_instance)
        
        # 初始化记忆管理器
        self.memory_manager = MemoryManager(short_memory_backend, long_memory_backend)
        self.memory_manager.set_long_memory_threshold(long_memory_importance_threshold)
        
        self.context_history = []
        self.is_active = False
        
        print(f"MCPContextManager初始化成功，用户ID: {user_id}")
    
    def __enter__(self):
        """
        进入上下文管理
        加载现有的上下文信息
        """
        self.is_active = True
        # 加载短期记忆并确保格式统一
        memories = self.memory_manager.get_short_memory(self.user_id)
        self.context_history = self._normalize_messages_format(memories)
        print(f"进入上下文，已加载{len(self.context_history)}条短期记忆")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出上下文管理
        保存上下文信息
        """
        # 保存短期记忆
        if self.context_history:
            self.memory_manager.store_short_memory(self.user_id, self.context_history)
            print(f"退出上下文，已保存{len(self.context_history)}条短期记忆到短期存储")
        
        self.is_active = False
        # 如果有异常，返回False让异常继续传播
        return False
    
    @contextmanager
    def active_context(self):
        """
        提供一个临时激活上下文的方法
        可在不使用with语句的情况下使用
        """
        was_active = self.is_active
        if not was_active:
            self.__enter__()
        
        try:
            yield self
        finally:
            if not was_active:
                self.__exit__(None, None, None)
    
    def add_message(self, message: Dict[str, Any], importance_score: float = 0.0):
        """
        添加消息到上下文
        
        Args:
            message: 消息字典，应包含type和content字段
            importance_score: 重要性分数，超过阈值会保存到长期记忆
            
        Returns:
            bool: 添加是否成功
        """
        try:
            # 确保消息格式正确，强制包含必要字段
            if not isinstance(message, dict):
                # 尝试从对象获取属性
                message_dict = {
                    "message_id": str(uuid.uuid4()),  # 生成唯一ID
                    "type": getattr(message, "type", "human"),
                    "content": getattr(message, "content", ""),
                    "timestamp": datetime.now().isoformat(),
                    "additional_kwargs": getattr(message, "additional_kwargs", {}),
                    "name": getattr(message, "name", None),
                    "importance_score": importance_score
                }
            else:
                # 确保包含所有必要字段
                message_dict = {
                    "message_id": message.get("message_id", str(uuid.uuid4())),
                    "type": message.get("type", "human"),
                    "content": message.get("content", ""),
                    "timestamp": message.get("timestamp", datetime.now().isoformat()),
                    "additional_kwargs": message.get("additional_kwargs", {}),
                    "name": message.get("name", None),
                    "importance_score": importance_score
                }
            
            # 添加到上下文历史
            self.context_history.append(message_dict)
            
            # 调用记忆管理器添加消息
            result = self.memory_manager.add_message(self.user_id, message_dict, importance_score)
            
            if importance_score >= self.memory_manager.long_memory_importance_threshold:
                print(f"消息重要性为{importance_score}，已保存到长期记忆")
            
            return result
            
        except Exception as e:
            print(f"添加消息到上下文时出错: {str(e)}")
            return False
    
    def add_user_message(self, content: str, importance_score: float = 0.0):
        """
        添加用户消息到上下文
        
        Args:
            content: 用户消息内容
            importance_score: 重要性分数
            
        Returns:
            bool: 添加是否成功
        """
        message = {
            "message_id": str(uuid.uuid4()),
            "type": "human",
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "additional_kwargs": {},
            "name": "user"
        }
        return self.add_message(message, importance_score)
    
    def get_context(self, include_long_memory: bool = False, limit: int = None):
        """
        获取会话上下文
        
        Args:
            include_long_memory: 是否包含长期记忆
            limit: 返回消息的数量限制
            
        Returns:
            List[Dict[str, Any]]: 上下文消息列表
        """
        # 先获取短期记忆（上下文历史）
        messages = self.context_history.copy()
        
        # 如果需要包含长期记忆
        if include_long_memory:
            try:
                # 从记忆管理器获取长期记忆
                long_term_memories = self.memory_manager.get_long_memory(self.user_id)
                # 合并长期记忆和短期记忆，避免重复
                all_messages = messages + long_term_memories
                # 按时间戳排序
                all_messages.sort(key=lambda x: x.get('timestamp', datetime.now().isoformat()))
                messages = all_messages
            except Exception as e:
                print(f"获取长期记忆时出错: {str(e)}")
        
        # 如果设置了限制，只返回最新的消息
        if limit and len(messages) > limit:
            messages = messages[-limit:]
        
        return messages
    
    def add_ai_message(self, content: str, importance_score: float = 0.0):
        """
        添加AI消息到上下文
        
        Args:
            content: AI消息内容
            importance_score: 重要性分数
            
        Returns:
            bool: 添加是否成功
        """
        message = {
            "message_id": str(uuid.uuid4()),
            "type": "ai",
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "additional_kwargs": {},
            "name": "assistant"
        }
        return self.add_message(message, importance_score)
    
    def get_stats(self):
        """
        获取会话统计信息
        
        Returns:
            Dict[str, int]: 包含短期记忆和长期记忆数量的字典
        """
        try:
            # 获取短期记忆数量
            short_memory_count = len(self.context_history)
            
            # 获取长期记忆数量
            long_memory_count = 0
            try:
                long_memories = self.memory_manager.get_long_memory(self.user_id)
                long_memory_count = len(long_memories)
            except Exception as e:
                print(f"获取长期记忆数量时出错: {str(e)}")
            
            return {
                'short_memory_count': short_memory_count,
                'long_memory_count': long_memory_count
            }
        except Exception as e:
            print(f"获取统计信息时出错: {str(e)}")
            return {
                'short_memory_count': len(self.context_history),
                'long_memory_count': 0
            }
    
    def _normalize_messages_format(self, memories):
        """
        确保所有消息格式统一
        
        Args:
            memories: 消息列表或字典
            
        Returns:
            List[Dict[str, Any]]: 标准化的消息列表
        """
        # 处理空输入
        if not memories:
            return []
            
        # 确保返回的是列表格式
        if isinstance(memories, dict):
            # 如果是字典格式，将其转换为列表
            return [memories]
            
        # 如果已经是列表格式，确保每个元素都有必要的字段
        normalized_messages = []
        for msg in memories:
            if isinstance(msg, dict):
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
            else:
                # 尝试从对象获取属性
                try:
                    normalized_msg = {
                        "message_id": str(uuid.uuid4()),
                        "type": getattr(msg, "type", "human"),
                        "content": getattr(msg, "content", ""),
                        "timestamp": datetime.now().isoformat(),
                        "additional_kwargs": getattr(msg, "additional_kwargs", {}),
                        "name": getattr(msg, "name", None),
                        "importance_score": 0.0
                    }
                    normalized_messages.append(normalized_msg)
                except Exception:
                    # 如果无法从对象获取属性，跳过此消息
                    continue
                    
        return normalized_messages
    
    def get_context(self, include_long_memory: bool = False, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取完整的上下文信息，确保返回的消息格式统一
        
        Args:
            include_long_memory: 是否包含长期记忆
            limit: 返回的最大消息数量
            
        Returns:
            List[Dict[str, Any]]: 上下文消息列表，每条消息都包含message_id、type、content、timestamp等必要字段
        """
        # 使用记忆管理器获取组合记忆
        context = self.memory_manager.get_combined_memory(self.user_id, include_long_memory, limit)
        
        # 确保格式统一
        context = self._normalize_messages_format(context)
        
        # 限制返回的消息数量
        if len(context) > limit:
            context = context[-limit:]
        
        return context
    
    def search_context(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索上下文中的内容，确保返回的消息格式统一
        
        Args:
            query: 搜索关键词
            limit: 返回的最大结果数量
            
        Returns:
            List[Dict[str, Any]]: 匹配的消息列表，每条消息都包含message_id、type、content、timestamp等必要字段
        """
        # 使用记忆管理器搜索记忆
        combined_results = self.memory_manager.search_memory(self.user_id, query, limit)
        
        # 规范化格式
        combined_results = self._normalize_messages_format(combined_results)
            
        # 限制返回数量
        return combined_results[:limit]
    
    def get_recent_messages(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        获取最近的几条消息，确保返回的消息格式统一
        
        Args:
            count: 消息数量
            
        Returns:
            List[Dict[str, Any]]: 最近的消息列表，每条消息都包含message_id、type、content、timestamp等必要字段
        """
        recent_messages = self.context_history[-count:] if self.context_history else []
        return self._normalize_messages_format(recent_messages)
    
    def update_memory_importance(self, message_content: str, importance_score: float):
        """
        更新记忆的重要性分数
        注意：此方法仅适用于长期记忆
        
        Args:
            message_content: 消息内容
            importance_score: 新的重要性分数
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 搜索包含该内容的长期记忆
            results = self.long_memory.search_memory(self.user_id, message_content, limit=10)
            
            success = False
            for result in results:
                # 由于我们没有直接的memory_id，这里需要先获取所有记忆并查找
                # 注意：实际应用中可能需要更精确的匹配方法
                if message_content in result.get('content', ''):
                    # 这里简化处理，实际可能需要额外的查询来获取memory_id
                    # 或者修改longmemory.py提供按内容更新的方法
                    print(f"警告：无法直接更新重要性分数，缺少memory_id")
                    return False
            
            return success
            
        except Exception as e:
            print(f"更新记忆重要性时出错: {str(e)}")
            return False
    
    def clear_short_memory(self):
        """
        清除短期记忆
        
        Returns:
            bool: 清除是否成功
        """
        try:
            # 假设记忆管理器有相应方法，否则直接调用底层实例
            if hasattr(self.memory_manager, 'clear_short_memory'):
                result = self.memory_manager.clear_short_memory(self.user_id)
            else:
                # 回退到直接调用底层实例
                result = self.memory_manager.short_memory.short_memory.delete_memory(self.user_id)
            if result:
                self.context_history = []
                print(f"短期记忆已清除")
            return result
        except Exception as e:
            print(f"清除短期记忆时出错: {str(e)}")
            return False
    
    def clear_long_memory(self, specific_memory_id: Optional[int] = None):
        """
        清除长期记忆
        
        Args:
            specific_memory_id: 特定记忆的ID，不提供则清除整个会话的长期记忆
            
        Returns:
            bool: 清除是否成功
        """
        try:
            # 假设记忆管理器有相应方法，否则直接调用底层实例
            if hasattr(self.memory_manager, 'clear_long_memory'):
                result = self.memory_manager.clear_long_memory(self.user_id, specific_memory_id)
            else:
                # 回退到直接调用底层实例
                result = self.memory_manager.long_memory.long_memory.delete_memory(self.user_id, specific_memory_id)
            if result:
                print(f"{f'特定ID({specific_memory_id})的' if specific_memory_id else '用户'}长期记忆已清除")
            return result
        except Exception as e:
            print(f"清除长期记忆时出错: {str(e)}")
            return False
    
    def format_context_as_prompt(self, include_long_memory: bool = False) -> str:
        """
        将上下文格式化为提示文本
        
        Args:
            include_long_memory: 是否包含长期记忆
            
        Returns:
            str: 格式化的提示文本
        """
        context = self.get_context(include_long_memory)
        prompt_parts = []
        
        if context:
            prompt_parts.append("对话历史：")
            
            for msg in context:
                role = "用户" if msg.get('type') == 'human' else "助手"
                content = msg.get('content', '')
                prompt_parts.append(f"{role}: {content}")
            
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    # 已在文件上方定义了正确的get_stats方法，此处移除重复定义


# 全局实例管理函数
def get_mcp_context(user_id: str, **kwargs) -> MCPContextManager:
    """
    获取MCP上下文管理器实例
    
    Args:
        user_id: 用户标识符
        **kwargs: 其他配置参数
        
    Returns:
        MCPContextManager: 上下文管理器实例
    """
    return MCPContextManager(user_id, **kwargs)