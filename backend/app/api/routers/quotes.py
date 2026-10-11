import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db import get_db
from app.models.quote import QuoteBatch, QuoteItem, QuoteSource
from app.models.user import User
from app.schemas.quote import CompareRequest, QuoteBatchOut, QuoteItemConfirm, QuoteItemOut
from app.services import comparison, quote_parser

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


@router.get("/batches/{batch_id}", response_model=QuoteBatchOut)
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuoteBatch:
    batch = db.get(QuoteBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "批次不存在")
    return batch


@router.post("/batches/{batch_id}/sources", response_model=QuoteBatchOut)
async def upload_source(
    batch_id: int,
    file: UploadFile,
    supplier_name: str = "",
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
        supplier_name=supplier_name or os.path.splitext(file.filename or "")[0],
    )
    db.add(source)
    batch.status = "parsing"
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/sources/{source_id}/parse", response_model=list[QuoteItemOut])
def parse_source(
    source_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[QuoteItem]:
    """触发解析管道：格式路由 → 规则抽取 / LLM 结构化 → 生成待确认明细。"""
    source = db.get(QuoteSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报价来源不存在")
    source.parse_status = "parsing"
    db.commit()
    items = quote_parser.parse_source(source, db)
    if not items:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "解析失败，请人工录入明细"
        )
    return items


@router.post("/batches/{batch_id}/parse", response_model=list[QuoteItemOut])
def parse_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[QuoteItem]:
    """一键解析批次下全部来源。"""
    batch = db.get(QuoteBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "批次不存在")
    return quote_parser.parse_batch(batch_id, db)


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
    _sync_confirmed_status(item.source_id, db)
    return item


def _sync_confirmed_status(source_id: int, db: Session) -> None:
    """当批次内明细全部确认后，把批次状态推进到 confirmed。"""
    source = db.get(QuoteSource, source_id)
    if source is None:
        return
    batch_id = source.batch_id
    unconfirmed = (
        db.query(QuoteItem)
        .join(QuoteSource, QuoteItem.source_id == QuoteSource.id)
        .filter(QuoteSource.batch_id == batch_id, QuoteItem.confirmed.is_(False))
        .count()
    )
    total = (
        db.query(QuoteItem)
        .join(QuoteSource, QuoteItem.source_id == QuoteSource.id)
        .filter(QuoteSource.batch_id == batch_id)
        .count()
    )
    batch = db.get(QuoteBatch, batch_id)
    if batch is not None and total > 0 and unconfirmed == 0:
        batch.status = "confirmed"
        db.commit()


@router.post("/batches/{batch_id}/compare")
def compare_batch(
    batch_id: int,
    req: CompareRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """按权重配置对已确认明细计算比价排序，结果落库 Comparison。"""
    batch = db.get(QuoteBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "批次不存在")
    return comparison.compare_batch(db, batch_id, req.weight_config)