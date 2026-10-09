import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db import get_db
from app.models.quote import QuoteBatch, QuoteItem, QuoteSource
from app.models.user import User
from app.parsers import router as parser_router
from app.schemas.quote import CompareRequest, QuoteBatchOut, QuoteItemConfirm, QuoteItemOut

router = APIRouter(prefix="/api/quotes", tags=["quotes"])

ALLOWED_TYPES = {".xlsx", ".xls", ".docx", ".pdf", ".png", ".jpg", ".jpeg"}


@router.post("/batches", response_model=QuoteBatchOut)
def create_batch(
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuoteBatch:
    batch = QuoteBatch(name=name, uploader_id=user.id)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/batches", response_model=list[QuoteBatchOut])
def list_batches(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[QuoteBatch]:
    return db.query(QuoteBatch).order_by(QuoteBatch.created_at.desc()).all()


@router.post("/batches/{batch_id}/sources", response_model=QuoteBatchOut)
async def upload_source(
    batch_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuoteBatch:
    batch = db.get(QuoteBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "批次不存在")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不支持的文件类型: {ext}")

    os.makedirs(settings.upload_dir, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(settings.upload_dir, saved_name)
    content = await file.read()
    with open(saved_path, "wb") as f:
        f.write(content)

    source = QuoteSource(
        batch_id=batch_id,
        file_name=file.filename or saved_name,
        file_type=ext.lstrip("."),
        raw_file_url=saved_path,
        parse_status="pending",
    )
    db.add(source)
    batch.status = "parsing"
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/sources/{source_id}/parse", response_model=QuoteItemOut)
def parse_source(
    source_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuoteItem:
    """触发解析管道：格式路由 → 解析器 → LLM 结构化抽取 → 生成待确认明细。

    骨架阶段返回占位结果；管道实现见 app/parsers 与 app/services/llm。
    """
    source = db.get(QuoteSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报价来源不存在")
    source.parse_status = "parsing"
    db.commit()
    items = parser_router.parse_file(source.raw_file_url, source.file_type, db=db)
    source.parse_status = "success" if items else "failed"
    db.commit()
    if not items:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "解析失败，请人工录入")
    return items[0]


@router.get("/batches/{batch_id}/items", response_model=list[QuoteItemOut])
def list_items(
    batch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[QuoteItem]:
    return (
        db.query(QuoteItem)
        .join(QuoteSource, QuoteItem.source_id == QuoteSource.id)
        .filter(QuoteSource.batch_id == batch_id)
        .all()
    )


@router.put("/items/{item_id}/confirm", response_model=QuoteItemOut)
def confirm_item(
    item_id: int,
    req: QuoteItemConfirm,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuoteItem:
    item = db.get(QuoteItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "明细不存在")
    for k, v in req.model_dump().items():
        setattr(item, k, v)
    item.confirmed = True
    db.commit()
    db.refresh(item)
    return item


@router.post("/batches/{batch_id}/compare")
def compare_batch(
    batch_id: int,
    req: CompareRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """按权重配置对已确认明细计算比价排序。骨架阶段返回占位结果。"""
    batch = db.get(QuoteBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "批次不存在")
    return {"batch_id": batch_id, "weights": req.weight_config, "result": [], "message": "比价引擎待实现（P3）"}
