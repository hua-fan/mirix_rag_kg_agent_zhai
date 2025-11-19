from typing import Optional, List, Dict, Any
from kg_tools_prompt import _build_intelligent_system_prompt

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
        self.kg_tools_tmpl = "{kg_tools_context}"
        
        # 最终整合模板
        self.final_tmpl = """
下列内容为对话的记忆：
{memory_section}

根据下列参考资料回答用户问题,参考资料中越靠前的内容相关度越高：
{rag_section}

知识图谱信息：
{kg_section}

用户问题：{query}

请基于对话历史、参考资料和知识图谱信息提供准确的回答，如果没有相关信息，则分析用户问题的意图，并尝试提供回答，回答内容注意以下规则：
1.回答内容非必要不得出现特殊符号，如*等。
2.回答语气为真人口吻，人设为可爱女生。
"""

    def _format_section(self, content: Optional[str], template: str, default: str = "暂无") -> str:
        """辅助方法：格式化单个部分，如果内容为空则返回默认值或空字符串"""
        if not content:
            return default
        return template.format(memory_context=content, rag_context=content, kg_context=content)

    def build_final_prompt(
        self, 
        query: str, 
        memory_context: str = "", 
        rag_context: str = "", 
        kg_context: str = ""
    ) -> str:
        """
        构建最终 Prompt
        Args:
            query: 用户问题
            memory_context: 记忆上下文（字符串）
            rag_context: RAG 检索到的文档（字符串）
            kg_context: 知识图谱查询结果（字符串）
        """
        # 渲染各部分，如果为空则留白或显示提示
        memory_section = self._format_section(memory_context, self.memory_tmpl, default="暂无相关记忆")
        rag_section = self._format_section(rag_context, self.rag_tmpl, default="无参考资料")
        kg_section = self._format_section(kg_context, self.kg_tmpl, default="知识图谱中未找到相关信息")

        # 组装最终 Prompt
        return self.final_tmpl.format(
            memory_section=memory_section,
            rag_section=rag_section,
            kg_section=kg_section,
            query=query
        )

    
    def get_kg_tools_prompt(self, memory_context: str) -> str:
        """
        获取知识图谱工具提示
        """
        return _build_intelligent_system_prompt(memory_context)
