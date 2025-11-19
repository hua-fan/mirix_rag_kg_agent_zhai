
def build_mirix_memory_prompt(mirix_agent=None,user_id=None,conversation_buffer=""):
    """构建包含MIRIX记忆上下文的提示
    Args:
        mirix_agent: MIRIX代理
        user_id: 用户ID
        conversation_buffer: 最近的对话记录(字符串格式)
    Returns:
        包含MIRIX记忆上下文的提示字符串
    """
    system_prompt = """ """
    if mirix_agent and user_id and conversation_buffer:
        memory_context = mirix_agent.extract_memory_for_system_prompt(
            conversation_buffer, user_id
        )
        if memory_context:
            system_prompt += "\n\n相关记忆上下文：\n" + memory_context
    return system_prompt
