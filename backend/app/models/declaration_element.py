from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DeclarationElement(Base):
    """申报要素库：一行代表某客户某产品的一个版本记录。"""

    __tablename__ = "declaration_element"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    hs_code: Mapped[str] = mapped_column(String(32), index=True)
    product_name: Mapped[str] = mapped_column(String(255), index=True)
    name_en: Mapped[str] = mapped_column(String(255), default="")
    customer_name: Mapped[str] = mapped_column(String(128), index=True)
    brand: Mapped[str] = mapped_column(String(128), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    spec: Mapped[str] = mapped_column(String(255), default="")
    material: Mapped[str] = mapped_column(String(255), default="")
    usage: Mapped[str] = mapped_column(String(255), default="")
    # 其余申报要素（JSON 数组：[{name, value}]）
    elements_json: Mapped[str] = mapped_column(Text, default="[]")
    source_file_url: Mapped[str] = mapped_column(String(512), default="")
    created_by: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
