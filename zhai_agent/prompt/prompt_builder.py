from typing import Optional, List, Dict, Any
from .kg_tools_prompt import _build_intelligent_system_prompt
from .kg_search_prompt import _build_kg_search_prompt

class PromptBuilder:
    """
    Prompt构建器（无状态版）
    负责将各种上下文信息组装成最终发给 LLM 的提示词。
    """
    def __init__(self):
        # 定义模板
        self.memory_tmpl = "{memory_context}"
        self.rag_tmpl = "{rag_context}"
        self.kg_tmpl = "{kg_context}"
        # 新增：对话历史的子模板
        self.history_tmpl = "{chat_history}"
        
        self.kg_tools_tmpl = "{kg_tools_context}"
        
        # 最终整合模板
        self.final_tmpl = """
【长期记忆 / 用户画像】
{memory_section}

【短期对话历史】
{history_section}

【知识图谱信息】
{kg_section}

【参考资料】
(根据下列参考资料回答用户问题,参考资料中越靠前的内容相关度越高)
{rag_section}

用户当前问题：{query}

请基于对话历史、参考资料和知识图谱信息提供准确的回答。如果没有相关信息，则分析用户问题的意图，并尝试提供回答。

回答规则：
1. 回答语气为真人口吻，人设为可爱女生。
2. 回答内容不应该与之前的回答有过多重复信息。
"""

    def _format_section(self, content: Optional[str], template: str, default: str = "暂无") -> str:
        """辅助方法：格式化单个部分，如果内容为空则返回默认值或空字符串"""
        if not content:
            return default
        return template.format(
            memory_context=content, 
            rag_context=content, 
            kg_context=content, 
            chat_history=content # 新增这个 key
        )

    def build_final_prompt(
        self, 
        query: str, 
        chat_history: str = "",
        memory_context: str = "", 
        rag_context: str = "", 
        kg_context: str = ""
    ) -> str:
        """
        构建最终 Prompt
        Args:
            query: 用户问题
            memory_context: 记忆上下文（字符串）
            chat_history:短期对话历史（字符串）
            rag_context: RAG 检索到的文档（字符串）
            kg_context: 知识图谱查询结果（字符串）
        """
        # 渲染各部分，如果为空则留白或显示提示
        memory_section = self._format_section(memory_context, self.memory_tmpl, default="暂无相关记忆")
        history_section = self._format_section(chat_history, self.history_tmpl, default="（这是对话的开始）")
        rag_section = self._format_section(rag_context, self.rag_tmpl, default="无参考资料")
        kg_section = self._format_section(kg_context, self.kg_tmpl, default="知识图谱中未找到相关信息")

        # 组装最终 Prompt
        return self.final_tmpl.format(
            memory_section=memory_section,
            history_section=history_section,
            rag_section=rag_section,
            kg_section=kg_section,
            query=query
        )

    
    def get_kg_tools_prompt(self, memory_context: str) -> str:
        """
        获取知识图谱构建工具提示词
        """
        return _build_intelligent_system_prompt(memory_context)


    def get_kg_search_prompt(self, user_name:str,query: str) -> str:
        """
        获取知识图谱查询工具提示词
        """
        return _build_kg_search_prompt(user_name=user_name,query=query)


def get_prompt_builder() -> PromptBuilder:
    """
    获取 PromptBuilder 实例的工厂函数
    """
    return PromptBuilder()
       
        