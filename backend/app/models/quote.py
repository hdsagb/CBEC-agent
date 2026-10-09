from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class QuoteBatch(Base):
    """一次比价批次：包含多家供应商报价来源与最终比价结果。"""

    __tablename__ = "quote_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    uploader_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    # uploaded | parsing | parsed | confirmed | compared
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuoteSource(Base):
    """一个报价来源：一份上传文件（一家供应商）。"""

    __tablename__ = "quote_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("quote_batch.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))  # xlsx | word | pdf | image | online
    raw_file_url: Mapped[str] = mapped_column(String(512))
    # pending | parsing | success | failed
    parse_status: Mapped[str] = mapped_column(String(32), default="pending")
    supplier_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuoteItem(Base):
    """报价明细行：解析出的单个产品报价，含置信度与人工确认标记。"""

    __tablename__ = "quote_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("quote_source.id"), index=True)
    product_name: Mapped[str] = mapped_column(String(255), default="")
    spec: Mapped[str] = mapped_column(String(255), default="")
    unit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    moq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_until: Mapped[str] = mapped_column(String(32), default="")
    remarks: Mapped[str] = mapped_column(String(512), default="")
    # LLM 抽取置信度 0~1
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    confirmed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Comparison(Base):
    """比价结果：按权重配置计算后的排序与推荐。"""

    __tablename__ = "comparison"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("quote_batch.id"), index=True)
    weight_config_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="[]")
    recommended_source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
