import json
import logging
from typing import Dict, Any, List
from zhai_agent.models.chat_state import ChatState
from zhai_agent.rag.rag_manager import RAGManager
from zhai_agent.prompt.prompt_builder import PromptBuilder
from zhai_agent.mirix_memory.memory_agent import MirixMemoryAgent
from zhai_agent.kg.kg_manager import KGManager
from langchain_core.messages import AIMessage, HumanMessage
from zhai_agent.utils.trans_messages_to_string import trans_messages_to_string
from langchain.schema import Document
from zhai_agent.prompt.mirix_memory_prompt import build_mirix_memory_prompt
from zhai_agent.kg.kg_tools import get_kg_tools
from langchain_core.utils.function_calling import convert_to_openai_tool
from zhai_agent.memory.MCPContextManager import get_mcp_context

# 配置日志
logger = logging.getLogger(__name__)

class WorkflowNodes:
    """
    工作流节点类，封装各种工作流节点的逻辑
    """
    
    def __init__(self, rag_manager: RAGManager, retriever=None, prompt_builder: PromptBuilder = None, mirix_agent: MirixMemoryAgent = None):
        """
        初始化工作流节点
        Args:
            rag_manager: RAG管理器实例
            retriever: 文档检索器
            prompt_builder: 提示构建器实例
            mirix_agent: Mirix记忆代理实例
        """
        self.rag_manager = rag_manager
        self.retriever = retriever
        self.context_managers = {}  # 存储不同会话的上下文管理器实例
        self.prompt_builder = prompt_builder or PromptBuilder()
        # 优先使用传入的mirix_agent参数，如果没有传入才创建默认实例
        self.mirix_agent = mirix_agent or MirixMemoryAgent()
        # 初始化知识图谱管理器
        self.kg_manager = KGManager()
        # 优化1: 预加载并缓存工具
        self.kg_tools = get_kg_tools()
    
        # 预先筛选查询类工具
        self.search_tools = [
            t for t in self.kg_tools 
            if t.name in ['kg_search_entities', 'kg_get_entity', 'kg_get_graph_stats']
        ]
        self.openai_search_tools = [convert_to_openai_tool(t) for t in self.search_tools]
        
        # 预先筛选构建类工具 (给 llm_kg_node 用)
        self.build_tools = [
            t for t in self.kg_tools 
            if t.name in ['kg_create_entity', 'kg_create_relationship'] # 根据实际工具名调整
        ]
        self.openai_build_tools = [convert_to_openai_tool(t) for t in self.build_tools]


    def llm_kg_node(self, state: ChatState) -> Dict[str, Any]:
        """
        【修改版】知识图谱构建节点
        职责：仅负责从用户对话中提取知识并存入图谱（写操作）。
        特点：不生成回复，不阻塞对话流，静默运行。
        """
        try:
            # 1. 获取用户输入
            user_message = state.messages[-1].content if state.messages else ""
            
            # 2. 构建专门的知识提取 Prompt
            # 强制 LLM 只关注提取信息，不要通过 content 说话
            system_prompt = self.prompt_builder.get_kg_tools_prompt(state.memory_context)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # 3. 调用 LLM (仅一轮，用于触发工具)
            llm_response = self.rag_manager.llm_client.create_chat_completion(
                messages=messages,
                tools=self.openai_build_tools,
                tool_choice="auto", # 让 LLM 决定是否需要提取
            )
            
            # 4. 处理工具调用
            tool_calls = llm_response.get("tool_calls")
            if tool_calls:
                logger.info(f"[KG Build] 正在提取知识，调用 {len(tool_calls)} 个工具")
                
                # 执行所有工具 (存入 Neo4j)
                tool_results = self._execute_tool_calls(tool_calls, self.kg_tools)
                
                # 记录日志即可，不需要将结果写回 state.messages 干扰聊天历史
                for res in tool_results:
                    logger.debug(f"工具执行结果: {res['result']}")
            else:
                logger.debug("[KG Build] 本轮对话无新知识需要提取")
                
            # 注意：这里直接返回 state，不对 state.messages 做任何修改
            # 这样它就像一个透明的过滤器

        except Exception as e:
            logger.error(f"知识图谱构建节点出错: {str(e)}")
            # 出错也不影响主流程
            
        return {}
        
    def chat_node(self, state: ChatState) -> Dict[str, Any]:
        """
        纯聊天节点，不调用工具，仅基于已有信息进行对话
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        try:
            # 获取最后一条用户消息
            if not state.messages:
                return state.model_dump()
            last_message = state.messages[-1]
            user_message = last_message.content if hasattr(last_message, 'content') else str(last_message)
            # 调用LLM生成回复
            ai_response = self._generate_response(user_message, state)
            # 创建AI消息并添加到状态
            ai_message = AIMessage(content=ai_response)
            state.messages.append(ai_message)
            
            logger.debug(f"纯聊天回复: {ai_response[:100]}...")
            
        except Exception as e:
            logger.error(f"聊天节点出错: {str(e)}")
            # 添加错误回复
            error_response = "抱歉，我在处理您的消息时遇到了问题。请稍后再试。"
            ai_message = AIMessage(content=error_response)
            state.messages.append(ai_message)
        
        return state.model_dump()
    
    def _get_memory_context(self, state: ChatState) -> str:
        """
        获取记忆上下文，优先使用mirix记忆
        """
        try:
            # 尝试获取mirix记忆
            user_name = state.user_name
            if user_name:
                conversation_buffer = trans_messages_to_string(state.messages[-10:])
                memory_context = self.mirix_agent.extract_memory_for_system_prompt(
                    conversation_buffer, user_name
                )
                if memory_context:
                    return f"用户记忆信息：\n{memory_context}"
        except Exception as e:
            logger.warning(f"获取mirix记忆失败: {str(e)}")
        
        # 回退到普通记忆
        try:
            user_id = state.user_id
            if user_id in self.context_managers:
                context_manager = self.context_managers[user_id]
                memories = context_manager.get_context(include_long_memory=True, limit=10)
                if memories:
                    return self._format_conversation_history(memories)
        except Exception as e:
            logger.warning(f"获取普通记忆失败: {str(e)}")
        
        return "暂无相关记忆信息"
    
    
    
    def _execute_tool_calls(self, tool_calls, available_tools) -> List[Dict[str, Any]]:
        """
        执行工具调用
        """
        results = []
        
        # 创建工具映射
        tool_map = {tool.name: tool for tool in available_tools if hasattr(tool, 'name')}
        
        for tool_call in tool_calls:
            try:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if function_name in tool_map:
                    tool = tool_map[function_name]
                    # 执行工具调用
                    result = tool.invoke(function_args)
                    results.append({
                        "call_id": tool_call.id,
                        "result": str(result)
                    })
                    logger.info(f"工具调用成功: {function_name} -> {result}")
                else:
                    results.append({
                        "call_id": tool_call.id,
                        "result": f"错误: 未找到工具 {function_name}"
                    })
                    
            except Exception as e:
                error_msg = f"工具调用失败: {str(e)}"
                logger.error(error_msg)
                results.append({
                    "call_id": tool_call.id,
                    "result": error_msg
                })
        
        return results

    def rag_node(self, state: ChatState) -> Dict[str, Any]:
        """
        RAG节点，用于从知识库提取相关文档
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        # 获取用户最后一条消息
        if state.messages:
            last_message = state.messages[-1]
            user_message = last_message.content if hasattr(last_message, 'content') else str(last_message)
        else:
            user_message = ""
        state.query = user_message
        # 执行文档检索
        retrieved_docs = self._retrieve_documents(user_message)
        state.retrieved_documents = [
            {"content": doc.page_content, "metadata": doc.metadata}
            for doc in retrieved_docs
        ]
        # 对检索到的文档进行重排
        sorted_docs = self._rerank_documents(retrieved_docs, user_message)
        
        # 将文档列表转换为字符串格式
        rag_context_str = ""
        for i, doc in enumerate(sorted_docs, 1):
            rag_context_str += f"参考资料{i}：{doc.page_content}\n"
        
        # 修改点：不再调用 self.prompt_builder.build_rag_prompt
        # 而是更新 state
        state.rag_context = rag_context_str

        return {"rag_context": rag_context_str}


    def mirix_memory_node(self, state:ChatState) -> Dict[str, Any]:
        """
        MIRIX记忆节点，用于从MIRIX代理提取记忆上下文
        Args:
            state: 聊天状态
        Returns:
            更新后的状态字典
        """
        # 获取用户姓名
        user_name = state.user_name
        # 从MIRIX代理提取记忆上下文
        memory_context = build_mirix_memory_prompt(
            self.mirix_agent,
            user_name,
            trans_messages_to_string(state.messages)
        )
        state.memory_context = memory_context
        
        return state.model_dump()

    def kg_search_node(self, state: ChatState) -> Dict[str, Any]:
        """
        知识图谱搜索节点 - 完全由LLM决策查询策略
        流程：分析用户需求 → LLM自主选择知识图谱工具查询 → 监控工具调用并整合结果
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        try:
            # 获取用户消息
            if state.messages:
                last_message = state.messages[-1]
                user_message = last_message.content if hasattr(last_message, 'content') else str(last_message)
            else:
                user_message = ""
            
            # 构建系统提示
            system_prompt = self.prompt_builder.get_kg_search_prompt(state.memory_context)
                
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # 调用支持工具的LLM进行查询
            llm_response = self.rag_manager.llm_client.create_chat_completion(
                messages=messages,
                tools=self.openai_search_tools,
                tool_choice="auto",
                temperature=0.1
            )
            
            # 处理工具调用
            tool_usage_info = []
            
            if llm_response.get("tool_calls"):
                logger.info(f"LLM调用 {len(llm_response['tool_calls'])} 个知识图谱工具")
                
                # 执行工具调用
                tool_results = self._execute_tool_calls(llm_response["tool_calls"], self.kg_tools)
                
                # 收集查询结果
                for i, tool_result in enumerate(tool_results):
                    tool_call = llm_response["tool_calls"][i]
                    tool_name = getattr(tool_call.function, 'name', 'unknown') if hasattr(tool_call, 'function') else 'unknown'
                    tool_usage_info.append(f"工具: {tool_name}, 结果: {str(tool_result['result'])[:200]}")
            else:
                logger.info("LLM未调用任何知识图谱工具")
                tool_usage_info.append("未调用知识图谱工具")
            
            # 整合查询结果
            kg_context_str = "\n".join(tool_usage_info) if tool_usage_info else "知识图谱中无相关信息"
            
            # 将查询结果添加到状态
            state.kg_context = kg_context_str
            
        except Exception as e:
            error_msg = f"知识图谱搜索出错: {str(e)}"
            logger.error(error_msg)
            
            # 错误处理
            error_context = f"知识图谱查询出错: {str(e)}"
            kg_context_str = error_context
            
            # 将错误信息添加到提示词构建器
            self.prompt_builder.kg_tmpl = error_context
        
        return {"kg_context": kg_context_str}

    def normal_memory_node(self, state: ChatState) -> Dict[str, Any]:
        """
        普通记忆节点，用于获取基于用户ID的记忆上下文
        Args:
            state: 聊天状态
        Returns:
            更新后的状态字典
        """
        # 使用user_id作为会话标识符
        user_id = state.user_id
        
        # 如果用户还没有上下文管理器，创建一个
        if user_id not in self.context_managers:
            self.context_managers[user_id] = get_mcp_context(
                user_id=user_id,
                redis_password='huafan123',
                pg_password='huafan123'
            )
        
        # 获取当前用户的上下文管理器
        context_manager = self.context_managers[user_id]
        
        # 从上下文管理器获取记忆（包括短期和长期记忆）
        previous_messages = context_manager.get_context(include_long_memory=True, limit=10)
        logger.debug(f"从MCPContextManager加载的消息数量: {len(previous_messages)}")
        
        # 格式化对话历史
        conversation_history = self._format_conversation_history(previous_messages)

        self.prompt_builder.build_memory_prompt(conversation_history)
        
        return state.model_dump()


    def _retrieve_documents(self, user_message: str) -> List[Document]:
        """
        检索相关文档
        Args:
            user_message: 用户消息
        Returns:
            List[Document]: 检索到的文档列表
        """
        retrieved_docs = []
        # 如果有检索器，执行文档检索
        if self.retriever:
            # 检索相关文档
            retrieved_docs = self.rag_manager.retrieve_documents(self.retriever, user_message)
            logger.debug(f"已检索到 {len(retrieved_docs)} 个相关文档片段")
        else:
            logger.debug("未使用RAG增强，无文档检索步骤")
        return retrieved_docs
    

    def _rerank_documents(self, retrieved_docs: List[Document], user_message: str) -> List[Document]:
        """
        对检索到的文档进行重排
        Args:
            retrieved_docs: 检索到的文档列表
            user_message: 用户消息
        Returns:
            List[Document]: 重排后的文档列表
        """
        return self.rag_manager.reRank(retrieved_docs, user_message)
    

    def _format_conversation_history(self, previous_messages: List[HumanMessage | AIMessage]) -> str:
        """
        格式化对话历史
        Args:
            previous_messages: 历史消息列表
        Returns:
            str: 格式化的对话历史
        """
        conversation_history = ""
        if previous_messages:
            for msg in previous_messages:
                if msg.type == 'human':
                    conversation_history += f"用户: {msg.content}\n"
                elif msg.type == 'ai':
                    conversation_history += f"助手: {msg.content}\n"
            # 移除最后一个换行符
            if conversation_history:
                conversation_history = conversation_history.rstrip('\n')
            logger.debug("已添加对话历史到提示中")
        else:
            logger.debug("无对话历史")
        return conversation_history


    def _generate_response(self, query: str, state: ChatState) -> str:
        """
        生成AI响应
        """
        # 此时是从 state 中读取数据，而不是从 prompt_builder 的内部变量读取
        final_prompt = self.prompt_builder.build_final_prompt(
            query=query,
            memory_context=state.memory_context,
            rag_context=state.rag_context,
            kg_context=state.kg_context
        )
        
        logger.debug(f"生成的最终提示:\n{final_prompt}")
        return self.rag_manager.call_llm(final_prompt)
    
    def store_mirix_memory_node(self, state: ChatState) -> Dict[str, Any]:
        """
        MIRIX记忆保存更新节点，基于用户姓名保存记忆
        Args:
            state: 聊天状态
        Returns:
            更新后的状态字典
        """
        # 使用user_name标识用户
        user_name = state.user_name
        self.mirix_agent.add_memory(trans_messages_to_string(state.messages), user_name=user_name)
        return state.model_dump()
      

    def store_memory_node(self, state: ChatState) -> Dict[str, Any]:
        """
        记忆存储节点，用于将对话内容保存到短期和长期记忆，基于用户ID保存
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        try:
            # 确保有足够的消息进行存储
            if len(state.messages) >= 2:
                # 获取最后一条用户消息和AI回复
                user_msg = state.messages[-2]
                ai_msg = state.messages[-1]
                # 使用user_id作为会话标识
                user_id = state.user_id
                
                # 检查是否有该用户的上下文管理器
                if user_id in self.context_managers:
                    context_manager = self.context_managers[user_id]
                    
                    # 使用上下文管理器存储消息
                    self._store_messages(context_manager, user_msg, ai_msg)
                    
                    # 获取并打印统计信息
                    stats = context_manager.get_stats()
                    logger.info(f"用户{user_id}统计: 短期记忆{stats['short_memory_count']}条, 长期记忆{stats['long_memory_count']}条")
        except Exception as e:
            logger.error(f"保存对话到记忆时出错: {str(e)}")
        return state.model_dump()

    
    def _store_messages(self, context_manager, user_msg, ai_msg):
        """
        存储用户消息和AI回复
        Args:
            context_manager: 上下文管理器实例
            user_msg: 用户消息
            ai_msg: AI回复
        """
        # 保存用户消息
        context_manager.add_user_message(
            content=getattr(user_msg, 'content', ''),
            importance_score=0.5  # 中等重要性
        )
        
        # 保存AI回复
        context_manager.add_ai_message(
            content=getattr(ai_msg, 'content', ''),
            importance_score=0.5  # 中等重要性
        )
        
        user_id = context_manager.user_id
        logger.debug(f"对话内容已通过MCPContextManager保存到用户: {user_id}")
    

  