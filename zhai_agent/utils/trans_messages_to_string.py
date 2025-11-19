from typing import List, Dict, Any, Union
from langchain_core.messages import HumanMessage, AIMessage


def trans_messages_to_string(messages: List[Union[Dict[str, Any], HumanMessage, AIMessage]]) -> str:
    """
    构建记忆提示，将消息列表转换为字符串
    Args:
        messages: 消息列表（支持字典类型或消息对象）
    Returns:
        记忆提示字符串
    """
    conversation_history = ""
    for msg in messages:
        # 兼容字典类型和消息对象
        if isinstance(msg, dict):
            msg_type = msg.get('type', '')
            content = msg.get('content', '')
        else:
            msg_type = getattr(msg, 'type', '')
            content = getattr(msg, 'content', '')
        
        if msg_type == 'human':
            conversation_history += f"用户: {content}\n"
        elif msg_type == 'ai':
            conversation_history += f"助手: {content}\n"
    
    # 移除最后一个换行
    if conversation_history:
        conversation_history = conversation_history.rstrip('\n')
        
    return conversation_history
