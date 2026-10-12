from datetime import datetime

from pydantic import BaseModel, Field


class MarkTemplateOut(BaseModel):
    id: int
    name: str
    layout_json: str
    thumbnail_url: str

    model_config = {"from_attributes": True}


class MarkTemplateCreate(BaseModel):
    name: str
    layout_json: str = "{}"


class MarkTemplateUpdate(BaseModel):
    """模板局部更新：可视化编辑器保存时按需提交名称 / 版式。"""

    name: str | None = None
    layout_json: str | None = None


class MarkJobCreate(BaseModel):
    template_id: int
    order_no: str = ""
    total_boxes: int = Field(1, ge=1, le=10000)
    start_no: int = Field(1, ge=1)
    fields_json: str = "{}"


class MarkJobOut(BaseModel):
    id: int
    template_id: int
    order_no: str
    total_boxes: int
    start_no: int
    fields_json: str

    model_config = {"from_attributes": True}


class MarkExportRequest(BaseModel):
    job_id: int
    format: str = "pdf"  # pdf | png


class AssetOut(BaseModel):
    id: int
    type: str  # logo | qrcode | barcode
    file_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MarkPreviewRequest(BaseModel):
    """可视化编辑器的所见即所得预览：直接传版式，不落模板。"""

    layout_json: str = "{}"
    fields_json: str = "{}"
    order_no: str = "PREVIEW"
    total_boxes: int = Field(1, ge=1, le=10000)
    start_no: int = Field(1, ge=1)
    box_no: int = Field(1, ge=1)


class MarkPreviewResult(BaseModel):
    url: str
    width_px: int
    height_px: int
    message: str
