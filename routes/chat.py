"""
Chat API - AI assistant for FAQs and product recommendations.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lib.chat import chat

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=20)
    include_products: bool = True
    client_id: str = "default"


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Send messages and get AI reply."""
    try:
        msgs = [{"role": m.role, "content": m.content} for m in req.messages]
        reply = chat(msgs, include_products=req.include_products, client_id=req.client_id)
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
