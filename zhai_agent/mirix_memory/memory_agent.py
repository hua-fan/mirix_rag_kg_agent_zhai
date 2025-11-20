import logging
from typing import Dict, Any, Optional
from mirix import Mirix
import os
from ..config import settings

logger = logging.getLogger(__name__)





class MirixMemoryAgent:
    def __init__(self, api_key: str = None, model: str = None):
        logger.info(f"正在初始化MirixMemoryAgent实例...")
        
        self.api_key = api_key or settings.MIRIX_API_KEY
        self.model = model or settings.MIRIX_MODEL_NAME
        
        # 使用配置初始化
        self.mirix_agent = Mirix(api_key=self.api_key, model=self.model)
        logger.info(f"Mirix实例初始化完成")
        # 1. 基础重置：将全局根日志级别设为 INFO
        # 这样 neo4j, urllib3 等第三方库默认只会打印 INFO 及以上级别的日志
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            force=True 
        )

        # 2. 针对您自己的项目，开启 DEBUG 级别
        # 这样 zhai_agent 下的 logger.debug(...) 依然可以看到
        logging.getLogger("zhai_agent").setLevel(logging.DEBUG)


    def add_memory(self, memory: str, user_name: Optional[str] = None) -> Dict[str, Any]:
        """添加记忆，支持user_name参数"""
        try:
            if user_name:
                user_id = self.get_user_id(user_name)
                # 显式指定user_id关键字参数
                return self.mirix_agent.add(memory, user_id=user_id)
            else:
                return self.mirix_agent.add(memory)
        except Exception as e:  # 捕获所有可能的异常（如用户不存在、参数错误）
            logger.error(f"添加记忆失败: {e}")
            return {"status": "error", "message": str(e)}

    def _ensure_user_exists(self, user_name: str) -> None:
        """确保用户存在，如果不存在则创建"""
        # 正确逻辑：先查询用户，若返回None则创建
        user = self.mirix_agent.get_user_by_name(user_name)
        if user is None:  # 当用户不存在时，get_user_by_name返回None
            try:
                # 关键：参数名应为user_name，而非name
                self.mirix_agent.create_user(user_name=user_name)
                logger.info(f"创建新用户成功: {user_name}")
            except Exception as e:
                logger.error(f"创建用户失败: {e}")

    def extract_memory_for_system_prompt(self, conversation_buffer: str, user_name: str) -> Optional[str]:
        """提取用户记忆用于系统提示，确保用户存在"""
        self._ensure_user_exists(user_name)  # 先确保用户存在
        try:
            user_id = self.get_user_id(user_name)
            # 注意：extract_memory_for_system_prompt的第一个参数是对话缓冲区（conversation_buffer）
            return self.mirix_agent.extract_memory_for_system_prompt(conversation_buffer, user_id)
        except Exception as e:
            logger.error(f"提取记忆失败: {e}")
            return None

    def get_user_id(self, user_name: str) -> str:
        """获取用户ID，确保用户存在"""
        self._ensure_user_exists(user_name)  # 双重保险：获取前先确保用户存在
        user = self.mirix_agent.get_user_by_name(user_name)
        if user is None:
            # 如果仍为None，说明创建用户失败，主动抛错提示
            raise ValueError(f"用户 {user_name} 不存在且创建失败，请检查SDK配置")
        return user.id  # 此时user一定非None，可安全访问id