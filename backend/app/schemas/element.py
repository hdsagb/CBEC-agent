from datetime import datetime

from pydantic import BaseModel


class ElementOut(BaseModel):
    id: int
    version: int
    hs_code: str
    product_name: str
    name_en: str
    customer_name: str
    brand: str
    model: str
    spec: str
    material: str
    usage: str
    elements_json: str
    source_file_url: str
    created_by: int
    updated_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ElementPage(BaseModel):
    """分页信封：列表 + 总数，供前端分页器使用。"""

    items: list[ElementOut]
    total: int
    page: int
    page_size: int


class DeclarationText(BaseModel):
    """一键复制的报关格式文本。"""

    text: str


class ElementCreate(BaseModel):
    hs_code: str
    product_name: str
    name_en: str = ""
    customer_name: str
    brand: str = ""
    model: str = ""
    spec: str = ""
    material: str = ""
    usage: str = ""
    elements_json: str = "[]"
    source_file_url: str = ""


class ElementUpdate(BaseModel):
    hs_code: str | None = None
    product_name: str | None = None
    name_en: str | None = None
    customer_name: str | None = None
    brand: str | None = None
    model: str | None = None
    spec: str | None = None
    material: str | None = None
    usage: str | None = None
    elements_json: str | None = None
    source_file_url: str | None = None
