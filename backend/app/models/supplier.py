from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Supplier(Base):
    """供应商主数据：沉淀供应商档案，配合历史报价库支撑优选决策。

    供应商档案与报价数据通过 supplier_name 字符串关联（报价来源当前只存名称），
    因此不强制外键，删除档案不影响历史报价记录的留存。
    """

    __tablename__ = "supplier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    region: Mapped[str] = mapped_column(String(64), default="")
    main_category: Mapped[str] = mapped_column(String(128), default="")
    contact_name: Mapped[str] = mapped_column(String(64), default="")
    contact_phone: Mapped[str] = mapped_column(String(32), default="")
    contact_email: Mapped[str] = mapped_column(String(128), default="")
    # 综合评级 0~5，供优选排序参考
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    # active 合作中 | paused 暂停合作 | blacklisted 拉黑
    status: Mapped[str] = mapped_column(String(32), default="active")
    remarks: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)