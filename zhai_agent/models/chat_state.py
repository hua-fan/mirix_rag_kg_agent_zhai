# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ChatState(BaseModel):
    """
    聊天状态类，用于存储工作流中的状态信息
    """
    messages: List[Any] = Field(default_factory=list)
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    query: Optional[str] = None
    round: int = 0
    user_id: str = Field(default="0")
    session_id: str = Field(default="default_session")
    user_name : str = Field(default="default_user")
    memory_context: str = ""
    rag_context: str = ""
    kg_context: str = ""
