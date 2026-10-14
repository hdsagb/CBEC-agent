from datetime import datetime

from pydantic import BaseModel, Field


class SupplierOut(BaseModel):
    id: int
    name: str
    region: str
    main_category: str
    contact_name: str
    contact_phone: str
    contact_email: str
    rating: float
    status: str
    remarks: str
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierPage(BaseModel):
    """分页信封：列表 + 总数，供前端分页器使用。"""

    items: list[SupplierOut]
    total: int
    page: int
    page_size: int


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    region: str = ""
    main_category: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    rating: float = Field(default=0.0, ge=0, le=5)
    status: str = "active"
    remarks: str = ""


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    region: str | None = None
    main_category: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    status: str | None = None
    remarks: str | None = None


# ---------------- 历史报价库 ----------------

class CurrencyPriceStat(BaseModel):
    """同一币种内的价格统计，避免跨币种直接求平均导致口径失真。"""

    currency: str
    item_count: int
    avg_price: float
    min_price: float
    max_price: float


class SupplierQuoteStat(BaseModel):
    """按供应商名称聚合的历史报价概览，并回填主数据档案信息。"""

    supplier_name: str
    item_count: int
    priced_count: int
    batch_count: int
    product_count: int
    currencies: list[str]
    last_quote_at: datetime | None
    price_stats: list[CurrencyPriceStat]
    # 与主数据档案的关联（未建档时 supplier_id 为空）
    supplier_id: int | None = None
    status: str = ""
    rating: float = 0.0
    region: str = ""


class SupplierQuoteStatPage(BaseModel):
    items: list[SupplierQuoteStat]
    total: int
    page: int
    page_size: int


class SupplierQuoteItem(BaseModel):
    """历史报价明细行：来自已解析的报价来源，含所属批次信息。"""

    id: int
    supplier_name: str
    batch_id: int
    batch_name: str
    product_name: str
    spec: str
    unit_price: float | None
    currency: str
    moq: int | None
    lead_time_days: int | None
    confirmed: bool
    quote_time: datetime


class SupplierQuotePage(BaseModel):
    items: list[SupplierQuoteItem]
    total: int
    page: int
    page_size: int