# -*- coding: utf-8 -*-
import os
import openai
from config import settings


class LLMClient:
    """
    语言模型客户端，封装对各种语言模型的调用
    """
    
    def __init__(self, api_key=None, base_url=None, model_name="deepseek-chat"):
        """
        初始化语言模型客户端
        Args:
            api_key: API密钥，如果不提供则从环境变量获取
            base_url: API基础URL
            model_name: 模型名称
        """
         # 优先使用传入参数，其次使用配置文件
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = base_url or settings.DEEPSEEK_BASE_URL
        self.model_name = model_name or settings.DEEPSEEK_MODEL_NAME
        
        if not self.api_key:
            print("警告: 未检测到 DEEPSEEK_API_KEY，LLM 功能可能不可用。")
    
    def call_model(self, prompt, temperature=0.8, max_tokens=2000):
        """
        调用语言模型
        Args:
            prompt: 提示内容
            temperature: 温度参数，控制输出的随机性
            max_tokens: 最大生成令牌数
        Returns:
            str: 模型响应
        """
        try:
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            # 调用模型
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # 获取模型响应
            ai_response = response.choices[0].message.content
            return ai_response
            
        except Exception as e:
            # 错误处理
            error_message = f"调用语言模型时出错: {str(e)}"
            print(error_message)
            return error_message
    
    def create_chat_completion(self, messages, temperature=0.8, max_tokens=2000, tools=None, tool_choice=None):
        """
        创建聊天完成，支持工具调用
        Args:
            messages: 消息列表，格式为[{"role": "user/assistant/system", "content": "消息内容"}, ...]
            temperature: 温度参数
            max_tokens: 最大生成令牌数
            tools: 工具列表，格式为[{"type": "function", "function": {...}}, ...]
            tool_choice: 工具选择策略，可选值："none", "auto", "required", 或指定工具名
        Returns:
            dict: 包含模型响应和工具调用信息的字典
            {
                "content": str,  # 模型响应内容
                "tool_calls": List[dict],  # 工具调用列表
                "finish_reason": str  # 结束原因
            }
        """
        try:
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            # 构建请求参数
            request_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # 如果有工具，添加到请求参数
            if tools:
                request_params["tools"] = tools
                if tool_choice:
                    request_params["tool_choice"] = tool_choice
            
            # 调用模型
            response = client.chat.completions.create(**request_params)
            
            # 获取响应信息
            choice = response.choices[0]
            ai_response = choice.message.content or ""
            tool_calls = getattr(choice.message, 'tool_calls', []) or []
            finish_reason = choice.finish_reason
            
            return {
                "content": ai_response,
                "tool_calls": tool_calls,
                "finish_reason": finish_reason
            }
            
        except Exception as e:
            # 错误处理
            error_message = f"创建聊天完成时出错: {str(e)}"
            print(error_message)
            return {
                "content": error_message,
                "tool_calls": [],
                "finish_reason": "error"
            }


def get_llm_client(api_key=None, base_url=None, model_name="deepseek-chat"):
    """
    获取LLM客户端实例
    Args:
        api_key: API密钥
        base_url: API基础URL
        model_name: 模型名称
    Returns:
        LLMClient: 语言模型客户端实例
    """
    # 创建并返回客户端实例
    return LLMClient(api_key, base_url, model_name)