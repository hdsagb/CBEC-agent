from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LLMConfig(Base):
    """全局大模型配置（单行表，id 固定为 1）：全系统共用一套模型。"""

    __tablename__ = "llm_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 展示用提供方标识，如 openai / deepseek / moonshot / custom
    provider: Mapped[str] = mapped_column(String(32), default="openai")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    api_key_cipher: Mapped[str] = mapped_column(Text, default="")

    # 多模态（图片报价单）：留空表示不启用，回退本地 OCR
    vision_model: Mapped[str] = mapped_column(String(128), default="")
    vision_base_url: Mapped[str] = mapped_column(String(512), default="")
    vision_api_key_cipher: Mapped[str] = mapped_column(Text, default="")

    updated_by: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 最近一次连通性探测结果，供页面状态灯快速渲染
    last_status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
