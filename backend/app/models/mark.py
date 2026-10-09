from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MarkTemplate(Base):
    """箱唛模板：layout_json 描述唛头画布布局（区块、字段占位、尺寸）。"""

    __tablename__ = "mark_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    layout_json: Mapped[str] = mapped_column(Text, default="{}")
    thumbnail_url: Mapped[str] = mapped_column(String(512), default="")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MarkJob(Base):
    """箱唛生成任务：基于模板 + 订单信息 + 箱号范围生成。"""

    __tablename__ = "mark_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("mark_template.id"))
    order_no: Mapped[str] = mapped_column(String(64), default="")
    total_boxes: Mapped[int] = mapped_column(Integer, default=1)
    start_no: Mapped[int] = mapped_column(Integer, default=1)
    fields_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Asset(Base):
    """箱唛素材：logo / 二维码 / 条码等。"""

    __tablename__ = "asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(16))  # logo | qrcode | barcode
    file_url: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
