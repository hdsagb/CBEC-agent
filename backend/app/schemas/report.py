from pydantic import BaseModel


class SupplierTrendPoint(BaseModel):
    month: str
    supplier_name: str
    currency: str
    avg_price: float
    min_price: float
    max_price: float
    item_count: int


class SupplierPriceTrendOut(BaseModel):
    months: list[str]
    suppliers: list[str]
    currencies: list[str]
    points: list[SupplierTrendPoint]


class CategorySlice(BaseModel):
    hs_chapter: str
    label: str
    element_count: int
    customer_count: int
    share: float


class CategoryDistributionOut(BaseModel):
    total_elements: int
    slices: list[CategorySlice]


class SavingGroup(BaseModel):
    batch_id: int
    batch_name: str
    product_name: str
    spec: str
    currency: str
    best_supplier: str
    best_price: float | None
    max_price: float | None
    saving: float
    saving_rate: float


class CurrencySaving(BaseModel):
    currency: str
    total_savings: float
    group_count: int


class SavingsOut(BaseModel):
    total_savings: float
    by_currency: list[CurrencySaving]
    batch_count: int
    group_count: int
    groups: list[SavingGroup]