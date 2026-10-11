from datetime import datetime

from pydantic import BaseModel


class QuoteSourceOut(BaseModel):
    id: int
    batch_id: int
    file_name: str
    file_type: str
    raw_file_url: str
    parse_status: str
    supplier_name: str

    model_config = {"from_attributes": True}


class QuoteItemOut(BaseModel):
    id: int
    source_id: int
    product_name: str
    spec: str
    unit_price: float | None
    currency: str
    moq: int | None
    lead_time_days: int | None
    valid_until: str
    remarks: str
    confidence: float
    confirmed: bool

    model_config = {"from_attributes": True}


class QuoteItemConfirm(BaseModel):
    product_name: str
    spec: str
    unit_price: float | None = None
    currency: str = "CNY"
    moq: int | None = None
    lead_time_days: int | None = None
    valid_until: str = ""
    remarks: str = ""


class QuoteBatchOut(BaseModel):
    id: int
    name: str
    uploader_id: int
    status: str
    created_at: datetime
    sources: list[QuoteSourceOut] = []

    model_config = {"from_attributes": True}


class CompareRequest(BaseModel):
    # 批次 ID 由路径提供，body 中可选
    batch_id: int | None = None
    # 维度权重：{"price": 0.5, "moq": 0.2, "lead_time": 0.2, "confidence": 0.1}
    weight_config: dict[str, float] = {}
