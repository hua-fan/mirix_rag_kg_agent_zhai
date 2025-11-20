# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional,Annotated
import operator
from langgraph.graph.message import add_messages


class ChatState(BaseModel):
    """
    聊天状态类，用于存储工作流中的状态信息
    """
    #每次消息是追加而非覆盖
    messages: Annotated[List[Any], add_messages] = Field(default_factory=list)
    #每次检索结果为覆盖
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
   
    query: Optional[str] = None
    round: int = 0
    user_id: str = Field(default="0")
    session_id: str = Field(default="default_session")
    user_name : str = Field(default="default_user")
   
    short_memory_context :str = ""
    memory_context: str = ""
    rag_context: str = ""
    kg_context: str = ""
