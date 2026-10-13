from pydantic import BaseModel


class ToolCall(BaseModel):
    name: str
    arguments: dict = {}


class ToolResult(BaseModel):
    name: str
    result: dict


class ChatMessageIn(BaseModel):
    session_id: int | None = None
    content: str


class ChatMessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    tool_calls_json: str

    model_config = {"from_attributes": True}


class ChatSessionOut(BaseModel):
    id: int
    user_id: int
    title: str

    model_config = {"from_attributes": True}


class ChatSessionUpdate(BaseModel):
    title: str
