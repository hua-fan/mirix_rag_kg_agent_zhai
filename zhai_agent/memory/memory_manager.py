# -*- coding: utf-8 -*-
"""
记忆管理器模块
提供统一的记忆管理接口，抽象具体记忆实现细节
"""
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod


class MemoryBackend(ABC):
    """
    记忆后端抽象基类
    定义记忆后端需要实现的接口
    """
    
    @abstractmethod
    def add_memory(self, user_id: str, message: Dict[str, Any], importance_score: float = 0.0) -> bool:
        """添加记忆"""
        pass
    
    @abstractmethod
    def get_memory(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取记忆"""
        pass
    
    @abstractmethod
    def search_memory(self, user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索记忆"""
        pass


class ShortTermMemoryBackend(MemoryBackend):
    """
    短期记忆后端实现
    包装ShortMemory类
    """
    
    def __init__(self, short_memory_instance):
        self.short_memory = short_memory_instance
    
    def add_memory(self, user_id: str, message: Dict[str, Any], importance_score: float = 0.0) -> bool:
        return self.short_memory.add_message(user_id, message)
    
    def get_memory(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        # ShortMemory.get_memory只接受user_id参数，这里只传递user_id
        return self.short_memory.get_memory(user_id)[:limit]
    
    def search_memory(self, user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        # 短期记忆通常不支持复杂搜索，这里简单实现
        memories = self.get_memory(user_id, limit)
        return [msg for msg in memories if query.lower() in msg.get('content', '').lower()][:limit]


class LongTermMemoryBackend(MemoryBackend):
    """
    长期记忆后端实现
    包装LongMemory类
    """
    
    def __init__(self, long_memory_instance):
        self.long_memory = long_memory_instance
    
    def add_memory(self, user_id: str, message: Dict[str, Any], importance_score: float = 0.0) -> bool:
        return self.long_memory.add_message(user_id, message, importance_score)
    
    def get_memory(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self.long_memory.get_memory(user_id, limit)
    
    def search_memory(self, user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        return self.long_memory.search_memory(user_id, query, limit)


class MemoryManager:
    """
    记忆管理器
    统一管理不同类型的记忆后端，提供统一的记忆访问接口
    """
    
    def __init__(self, short_memory_backend: MemoryBackend, long_memory_backend: MemoryBackend):
        """
        初始化记忆管理器
        
        Args:
            short_memory_backend: 短期记忆后端
            long_memory_backend: 长期记忆后端
        """
        self.short_memory = short_memory_backend
        self.long_memory = long_memory_backend
        self.long_memory_importance_threshold = 0.5
    
    def add_message(self, user_id: str, message: Dict[str, Any], importance_score: float = 0.0) -> bool:
        """
        添加消息到记忆系统
        
        Args:
            user_id: 用户ID
            message: 消息内容
            importance_score: 重要性分数
            
        Returns:
            bool: 是否添加成功
        """
        # 始终添加到短期记忆
        short_result = self.short_memory.add_memory(user_id, message, importance_score)
        
        # 根据重要性决定是否添加到长期记忆
        long_result = True
        if importance_score >= self.long_memory_importance_threshold:
            long_result = self.long_memory.add_memory(user_id, message, importance_score)
        
        return short_result and long_result
    
    def get_combined_memory(self, user_id: str, include_long_memory: bool = False, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取组合记忆（短期+长期）
        
        Args:
            user_id: 用户ID
            include_long_memory: 是否包含长期记忆
            limit: 返回的最大消息数量
            
        Returns:
            List[Dict[str, Any]]: 消息列表
        """
        # 获取短期记忆
        context = self.short_memory.get_memory(user_id, limit)
        
        if include_long_memory:
            # 获取长期记忆
            long_memories = self.long_memory.get_memory(user_id, limit)
            
            # 合并并去重
            existing_ids = {msg.get('message_id', '') for msg in context}
            for mem in long_memories:
                if mem.get('message_id', '') not in existing_ids:
                    context.append(mem)
                    existing_ids.add(mem.get('message_id', ''))
        
        # 按时间排序并限制数量
        context.sort(key=lambda x: x.get('timestamp', ''), reverse=False)
        return context[-limit:]
    
    def search_memory(self, user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索记忆
        
        Args:
            user_id: 用户ID
            query: 搜索关键词
            limit: 返回的最大结果数量
            
        Returns:
            List[Dict[str, Any]]: 匹配的消息列表
        """
        # 搜索短期记忆
        short_results = self.short_memory.search_memory(user_id, query, limit)
        
        # 搜索长期记忆
        long_results = self.long_memory.search_memory(user_id, query, limit)
        
        # 合并结果并去重
        combined_results = short_results.copy()
        existing_ids = {msg.get('message_id', '') for msg in short_results}
        
        for result in long_results:
            if result.get('message_id', '') not in existing_ids:
                combined_results.append(result)
                existing_ids.add(result.get('message_id', ''))
        
        # 按时间排序并限制数量
        combined_results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return combined_results[:limit]
    
    def set_long_memory_threshold(self, threshold: float):
        """
        设置长期记忆的重要性阈值
        
        Args:
            threshold: 重要性阈值
        """
        self.long_memory_importance_threshold = threshold
    
    def get_short_memory(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取短期记忆
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[Dict[str, Any]]: 短期记忆列表
        """
        return self.short_memory.get_memory(user_id)
    
    def store_short_memory(self, user_id: str, messages: List[Dict[str, Any]]) -> bool:
        """
        存储短期记忆
        
        Args:
            user_id: 用户ID
            messages: 消息列表
            
        Returns:
            bool: 是否存储成功
        """
        if hasattr(self.short_memory, 'store_memory'):
            return self.short_memory.store_memory(user_id, messages)
        else:
            # 如果没有store_memory方法，尝试通过add_message逐条添加
            success = True
            for message in messages:
                if not self.short_memory.add_message(user_id, message):
                    success = False
            return success
    
    def get_long_memory(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取长期记忆
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[Dict[str, Any]]: 长期记忆列表
        """
        return self.long_memory.get_memory(user_id)