import json
from pickle import DICT
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
        # 优化2: 使用 LangChain 标准函数转换工具格式
        self.openai_tools = [convert_to_openai_tool(t) for t in self.kg_tools]


    def llm_kg_node(self, state: ChatState) -> Dict[str, Any]:
        """
        智能聊天节点：LLM 决策 -> (可选)调用 KG 工具 -> 生成回复
        """
        try:
            # 1. 获取用户输入
            user_message = state.messages[-1].content if state.messages else ""
            
            # 2. 获取记忆上下文
            memory_context = self._get_memory_context(state)
            
            # 3. 构建 Prompt 
            system_prompt = self._build_intelligent_system_prompt(memory_context)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # 4. 第一轮 LLM 调用：决策与工具调用
            # 使用预处理好的 self.openai_tools
            llm_response = self.rag_manager.llm_client.create_chat_completion(
                messages=messages,
                tools=self.openai_tools,
                tool_choice="auto",
                temperature=0.3
            )
            
            # 5. 处理工具调用 (ReAct 循环的第一步)
            tool_calls = llm_response.get("tool_calls")
            if tool_calls:
                print(f"🤖 LLM 决定调用 {len(tool_calls)} 个工具")
                
                # 将助手的思考过程加入历史
                messages.append({
                    "role": "assistant",
                    "content": llm_response.get("content") or "",  # content 可能为 None
                    "tool_calls": tool_calls
                })
                
                # 执行所有工具
                tool_results = self._execute_tool_calls(tool_calls, self.kg_tools)
                
                # 将工具结果加入历史
                for tool_result in tool_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_result["call_id"],
                        "content": str(tool_result["result"]) # 确保转换为字符串
                    })
                
                # 6. 第二轮 LLM 调用：根据工具结果生成最终回复
                final_response = self.rag_manager.llm_client.create_chat_completion(
                    messages=messages,
                    # 第二轮通常不需要再调用工具，除非实现多轮循环
                    tools=self.openai_tools, 
                    tool_choice="none", 
                    temperature=0.3
                )
                ai_response = final_response["content"]
            else:
                # 未调用工具，直接使用回复
                ai_response = llm_response["content"]
            
            # 7. 更新状态
            # 注意：这里应该将 AI 回复加入 state.messages，而不仅仅是返回
            from langchain_core.messages import AIMessage
            state.messages.append(AIMessage(content=ai_response))

        except Exception as e:
            print(f"❌ 智能聊天节点出错: {str(e)}")
            import traceback
            traceback.print_exc()
            # 错误恢复机制
            state.messages.append(AIMessage(content="抱歉，系统处理您的请求时遇到了一些技术问题。"))
            
        return state.model_dump()
        
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
            
            print(f"纯聊天回复: {ai_response[:100]}...")
            
        except Exception as e:
            print(f"聊天节点出错: {str(e)}")
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
            print(f"获取mirix记忆失败: {str(e)}")
        
        # 回退到普通记忆
        try:
            user_id = state.user_id
            if user_id in self.context_managers:
                context_manager = self.context_managers[user_id]
                memories = context_manager.get_context(include_long_memory=True, limit=10)
                if memories:
                    return self._format_conversation_history(memories)
        except Exception as e:
            print(f"获取普通记忆失败: {str(e)}")
        
        return "暂无相关记忆信息"
    
    def _build_intelligent_system_prompt(self, memory_context: str) -> str:
        """
        构建工具调用提示，传入记忆上下文进行辅助。
        """
        return self.prompt_builder.get_kg_tools_prompt(memory_context)
    
    
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
                    print(f"工具调用成功: {function_name} -> {result}")
                else:
                    results.append({
                        "call_id": tool_call.id,
                        "result": f"错误: 未找到工具 {function_name}"
                    })
                    
            except Exception as e:
                error_msg = f"工具调用失败: {str(e)}"
                print(error_msg)
                results.append({
                    "call_id": tool_call.id,
                    "result": error_msg
                })
        
        return results

    def query_kg_node(self,state:ChatState) -> Dict[str,Any]:
        """KG节点，用于查询知识图谱"""
        # 获取用户最后一条消息
        user_message = state.messages[-1].get('content', '') if state.messages else ""
        # 调用知识图谱查询接口
        kg_response = self.kg_manager.query_kg(user_message)
        # 将查询结果添加到消息列表
        state.messages.append(AIMessage(content=kg_response))


        return state.model_dump()

    def rag_node(self, state: ChatState) -> Dict[str, Any]:
        """
        RAG节点，用于从知识库提取相关文档
        Args:
            state: 聊天状态
        Returns:
            dict: 更新后的状态
        """
        # 获取用户最后一条消息
        user_message = state.messages[-1].get('content', '') if state.messages else ""
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

        return state.model_dump()


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
            
            # 构建详细的系统提示，明确指导LLM使用工具
            system_prompt = f"""你是一个知识图谱查询专家。你必须使用提供的工具来查询知识图谱，不能凭想象回答。

可用工具包括：
- kg_search_entities(keyword): 搜索包含关键词的实体（如人名、物品、概念等）
- kg_get_entity(entity_name): 获取实体的详细信息（属性、关系等）
- kg_get_graph_stats(): 获取知识图谱的整体统计信息

重要规则：
1. 对于用户关于个人喜好、属性、关系的问题，你必须先搜索相关实体
2. 如果找到实体，立即使用get_entity获取其详细信息
3. 使用工具获取真实数据，不能凭想象或假设回答
4. 如果搜索不到相关信息，要如实说明"在知识图谱中未找到相关信息"
5. 记住用户的名字和个人信息很重要，每次对话都要检查知识图谱

请严格按以下步骤操作：
1. 提取用户问题中的关键实体名称（如人名"繁花"）
2. 首先使用kg_search_entities搜索该实体（不指定实体类型）
3. 如果找不到，可以尝试指定常见类型如'person'再次搜索
4. 如果找到匹配实体，使用kg_get_entity获取其完整信息
5. 基于工具返回的真实数据回答用户问题

记忆信息（供参考）：
{self._get_memory_context(state)}

请根据用户的问题，智能地选择查询工具并执行查询。记住：必须使用工具获取真实数据！"""
            
            # 准备消息列表
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # 获取知识图谱工具，但只保留查询工具
            from zhai_agent.kg.kg_tools import get_kg_tools
            all_tools = get_kg_tools()
            
            print(f"获取到 {len(all_tools)} 个工具")
            
            # 详细检查每个工具
            for i, tool in enumerate(all_tools):
                tool_name = getattr(tool, 'name', f'unknown_{i}')
                tool_type = type(tool)
                print(f"工具 {i}: name='{tool_name}', type={tool_type}")
            
            # 调试：直接查看知识图谱中的实体统计
            try:
                from zhai_agent.kg.kg_tools import get_graph_stats
                stats = get_graph_stats({})
                print(f"\n📊 知识图谱统计: {str(stats)[:200]}...")
            except Exception as e:
                print(f"\n获取图谱统计失败: {e}")
            
            # 过滤出仅查询工具并记录
            query_tools = []
            for tool in all_tools:
                if hasattr(tool, 'name') and tool.name in ['kg_search_entities', 'kg_get_entity', 'kg_get_graph_stats']:
                    query_tools.append(tool)

            print(f"可用知识图谱查询工具: {[tool.name for tool in query_tools]}")
            
            # 如果没有找到工具，尝试使用所有工具
            if not query_tools:
                print("⚠️  未找到指定的查询工具，尝试使用所有工具...")
                query_tools = all_tools
                print(f"使用所有工具: {[getattr(tool, 'name', 'unknown') for tool in query_tools]}")
                
                # 如果仍然没有工具，创建模拟工具
                if not query_tools:
                    print("❌ 没有任何工具可用，创建模拟工具...")
                    # 这里可以添加模拟工具或错误处理
            
            # 将工具转换为OpenAI格式
            tools = self._convert_tools_to_openai_format(query_tools)
            
            # 调用支持工具的LLM进行查询 - 强制使用工具
            llm_response = self.rag_manager.llm_client.create_chat_completion(
                messages=messages,
                tools=tools,
                tool_choice="required",  # 强制LLM必须使用工具
                temperature=0.1  # 降低温度以提高确定性
            )
            
            # 详细监控工具调用情况
            tool_usage_info = []
            
            # 处理工具调用
            if llm_response.get("tool_calls"):
                print(f"\n✓ LLM决定调用 {len(llm_response['tool_calls'])} 个知识图谱查询工具")
                
                # 执行工具调用
                tool_results = self._execute_tool_calls(llm_response["tool_calls"], query_tools)
                
                # 收集所有查询结果并记录详细信息
                for i, tool_result in enumerate(tool_results):
                    tool_call = llm_response["tool_calls"][i]
                    # 正确处理ChatCompletionMessageFunctionToolCall对象
                    if hasattr(tool_call, 'function'):
                        tool_name = getattr(tool_call.function, 'name', 'unknown')
                        # 获取工具调用的参数
                        if hasattr(tool_call.function, 'arguments'):
                            try:
                                import json
                                args = json.loads(tool_call.function.arguments)
                                print(f"  - 工具 {i+1}: {tool_name} 参数: {args}")
                                
                                # 如果搜索实体未找到结果，尝试不指定类型的搜索
                                if tool_name == 'kg_search_entities' and '未找到包含' in str(tool_result['result']):
                                    print(f"  - 搜索未找到结果，尝试不指定实体类型的搜索...")
                                    # 重新搜索，不指定entity_type
                                    from zhai_agent.kg.kg_tools import search_entities
                                    retry_result = search_entities(args.get('keyword', ''))
                                    print(f"  - 重新搜索结果: {str(retry_result)[:200]}...")
                                    if '未找到包含' not in retry_result:
                                        tool_result['result'] = retry_result
                                        print(f"  - ✅ 重新搜索成功！")
                                    else:
                                        # 尝试直接查询所有实体
                                        print(f"  - 尝试直接查询所有实体...")
                                        try:
                                            from zhai_agent.kg.kg_storage import KGStorage
                                            storage = KGStorage()
                                            all_entities = storage.search_entities('繁花')
                                            print(f"  - 直接查询结果: 找到 {len(all_entities)} 个实体")
                                            for entity in all_entities[:5]:
                                                print(f"    - 实体: {entity.get('name', 'unknown')} (类型: {entity.get('type', 'unknown')})")
                                        except Exception as debug_e:
                                            print(f"  - 直接查询失败: {debug_e}")
                                    
                            except:
                                pass
                    else:
                        tool_name = 'unknown'
                    tool_usage_info.append(f"工具: {tool_name}, 结果: {str(tool_result['result'])[:200]}")
                    print(f"    结果: {str(tool_result['result'])[:200]}...")
            else:
                print(f"\n✗ LLM未调用任何工具！")
                print(f"  这可能是因为：")
                print(f"  1. LLM认为不需要查询知识图谱")
                print(f"  2. 系统提示不够明确")
                print(f"  3. 工具选择逻辑问题")
                tool_usage_info.append("LLM未调用任何工具")
            
            # 整合查询结果
            if tool_usage_info:
                kg_context_str = f"知识图谱查询情况:\n" + "\n".join(tool_usage_info)
            else:
                kg_context_str = "知识图谱中无相关信息"
            
            # 将查询结果添加到提示词构建器中
            state.kg_context = kg_context_str
            
        except Exception as e:
            error_message = f"知识图谱搜索节点出错: {str(e)}"
            print(error_message)
            import traceback
            traceback.print_exc()
            
            # 提供更有用的错误信息
            error_context = f"知识图谱查询出错: {str(e)}\n这可能是因为：\n1. 知识图谱中没有相关信息\n2. 实体名称拼写不同\n3. 该实体尚未被记录到知识图谱中\n建议：可以询问用户的具体喜好，然后记录下来。"
            
            # 将错误信息添加到提示词中
            self.prompt_builder.build_kg_prompt(error_context)
        
        return state.model_dump()

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
        print(f"从MCPContextManager加载的消息数量: {len(previous_messages)}")
        
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
            print(f"\n已检索到 {len(retrieved_docs)} 个相关文档片段")
        else:
            print("\n未使用RAG增强，无文档检索步骤")
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
            print("已添加对话历史到提示中")
        else:
            print("无对话历史")
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
        
        print(f"生成的最终提示:\n{final_prompt}")
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
                    print(f"用户{user_id}统计: 短期记忆{stats['short_memory_count']}条, 长期记忆{stats['long_memory_count']}条")
        except Exception as e:
            print(f"保存对话到记忆时出错: {str(e)}")
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
        print(f"对话内容已通过MCPContextManager保存到用户: {user_id}")
    

  