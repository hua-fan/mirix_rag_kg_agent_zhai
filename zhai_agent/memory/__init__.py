# -*- coding: utf-8 -*-
"""
记忆模块初始化文件
提供统一的记忆系统访问接口
"""
from zhai_agent.memory.shortmemory import ShortMemory
from zhai_agent.memory.longmemory import get_longmemory_instance
from zhai_agent.memory.MCPContextManager import get_mcp_context

__all__ = [
    'ShortMemory',
    'get_longmemory_instance',
    'get_mcp_context'
]