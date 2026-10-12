import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.chat import ChatMessageIn, ChatMessageOut, ChatSessionOut, ToolCall, ToolResult
from app.services.agent import AGENT_TOOLS, run_agent_turn

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/tools")
def list_tools(user: User = Depends(get_current_user)) -> list[dict]:
    return AGENT_TOOLS


@router.post("/sessions", response_model=ChatSessionOut)
def create_session(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatSession:
    session = ChatSession(user_id=user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ChatSession]:
    return db.query(ChatSession).filter(ChatSession.user_id == user.id).all()


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ChatMessage]:
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return db.query(ChatMessage).filter(ChatMessage.session_id == session_id).all()


@router.post("/chat", response_model=ChatMessageOut)
def chat(
    req: ChatMessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatMessage:
    """Agent 对话入口：LLM + Function Calling 调度 AGENT_TOOLS 中注册的业务工具。"""
    if req.session_id is None:
        session = ChatSession(user_id=user.id)
        db.add(session)
        db.commit()
        db.refresh(session)
    else:
        session = db.get(ChatSession, req.session_id)
        if session is None or session.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")

    session_id = session.id
    # 首条消息用作会话标题，避免会话列表全部显示默认名
    if session.title == "新会话" and req.content.strip():
        session.title = req.content.strip()[:20]
    # 持久化用户消息，保证刷新后仍能看到完整对话
    db.add(ChatMessage(session_id=session_id, role="user", content=req.content))
    db.commit()

    reply, tool_results = run_agent_turn(db, user, session_id)
    message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=reply,
        # 存为标准 JSON，前端可直接 JSON.parse
        tool_calls_json=json.dumps([r.model_dump() for r in tool_results], ensure_ascii=False),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
