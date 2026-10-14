from datetime import datetime

from pydantic import BaseModel, Field


class PriceReferenceSample(BaseModel):
    """历史价格样本：一条已确认报价明细及其来源信息。"""

    quote_item_id: int
    supplier_name: str
    product_name: str
    spec: str
    unit_price: float | None
    currency: str
    batch_id: int
    batch_name: str
    quote_time: datetime


class CurrencyPriceReference(BaseModel):
    """同一币种内的历史价格统计，避免跨币种直接求平均导致口径失真。"""

    currency: str
    item_count: int
    avg_price: float
    min_price: float
    max_price: float
    last_price: float
    last_quote_at: datetime


class PriceReference(BaseModel):
    """某商品/HS 编码下的历史价格参考汇总。"""

    hs_code: str
    product_name: str
    # product：按商品名精确命中；hs_code：同 HS 编码兜底；none：无历史参考
    match_by: str
    sample_count: int
    currency_stats: list[CurrencyPriceReference]
    samples: list[PriceReferenceSample]


class PriceCheckRequest(BaseModel):
    product_name: str = ""
    hs_code: str = ""
    unit_price: float | None = None
    # 留空表示沿用明细自身的币种
    currency: str = ""
    tolerance: float = Field(default=0.2, ge=0, le=1)
    only_confirmed: bool = True


class PriceCheckResult(BaseModel):
    """单条报价的合理性校验结果。"""

    # low | normal | high | no_reference
    verdict: str
    unit_price: float | None
    currency: str
    deviation_rate: float | None
    tolerance: float
    reference_avg: float | None
    reference_min: float | None
    reference_max: float | None
    sample_count: int
    match_by: str
    hs_code: str
    message: str


class BatchPriceCheckRequest(BaseModel):
    tolerance: float = Field(default=0.2, ge=0, le=1)
    only_confirmed: bool = True


class BatchPriceCheckItem(BaseModel):
    item_id: int
    supplier_name: str
    product_name: str
    spec: str
    unit_price: float | None
    currency: str
    verdict: str
    deviation_rate: float | None
    reference_avg: float | None
    sample_count: int
    match_by: str
    message: str


class BatchPriceCheckResult(BaseModel):
    """批次级价格校验：逐条判定 + 各判定数量汇总。"""

    batch_id: int
    tolerance: float
    total: int
    low: int
    normal: int
    high: int
    no_reference: int
    items: list[BatchPriceCheckItem]