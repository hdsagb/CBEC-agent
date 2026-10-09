from datetime import datetime

from pydantic import BaseModel


class MarkTemplateOut(BaseModel):
    id: int
    name: str
    layout_json: str
    thumbnail_url: str

    model_config = {"from_attributes": True}


class MarkTemplateCreate(BaseModel):
    name: str
    layout_json: str = "{}"


class MarkJobCreate(BaseModel):
    template_id: int
    order_no: str = ""
    total_boxes: int = 1
    start_no: int = 1
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
