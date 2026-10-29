import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db import get_db
from app.models.quote import QuoteBatch, QuoteItem, QuoteSource
from app.models.user import User
from app.schemas.price_reference import (
    BatchPriceCheckItem,
    BatchPriceCheckRequest,
    BatchPriceCheckResult,
    PriceCheckRequest,
    PriceCheckResult,
)
from app.schemas.quote import (
    CompareRequest,
    QuoteBatchOut,
    QuoteBatchPage,
    QuoteItemConfirm,
    QuoteItemOut,
)
from app.services import comparison, price_reference, quote_parser

router = APIRouter(prefix="/api/quotes", tags=["quotes"])

ALLOWED_TYPES = {".xlsx", ".xls", ".docx", ".pdf", ".png", ".jpg", ".jpeg"}
# 单个报价单上限：图片报价单最大，其余格式远小于此值
MAX_SOURCE_BYTES = 20 * 1024 * 1024


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


@router.get("/batches", response_model=QuoteBatchPage)
def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuoteBatchPage:
    """批次列表分页：按创建时间倒序，附带来源明细供前端展示报价份数。"""
    q = db.query(QuoteBatch)
    total = q.count()
    items = (
        q.order_by(QuoteBatch.created_at.desc(), QuoteBatch.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return QuoteBatchPage(items=items, total=total, page=page, page_size=page_size)


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
    # 先按声明的大小拦一次，避免把超大文件整体读进内存
    if file.size is not None and file.size > MAX_SOURCE_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"报价单不能超过 {MAX_SOURCE_BYTES // 1024 // 1024}MB",
        )

    os.makedirs(settings.upload_dir, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(settings.upload_dir, saved_name)
    content = await file.read()
    # 声明大小可能缺失或被伪造成小值，读入后再校验一次
    if len(content) > MAX_SOURCE_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"报价单不能超过 {MAX_SOURCE_BYTES // 1024 // 1024}MB",
        )
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "报价单内容为空")
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
    # 明细确认与批次状态推进放在同一个事务里：先 flush 让计数查询看到本次修改，
    # 再统一提交，避免两次 commit 之间失败导致「明细已确认、批次仍待确认」
    db.flush()
    _sync_confirmed_status(item.source_id, db)
    db.commit()
    db.refresh(item)
    return item


def _sync_confirmed_status(source_id: int, db: Session) -> None:
    """当批次内明细全部确认后，把批次状态标记为 confirmed（由调用方统一提交）。"""
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


def _price_check_row(
    db: Session,
    item: QuoteItem,
    source: QuoteSource | None,
    tolerance: float,
    only_confirmed: bool,
    exclude_batch_id: int | None,
    pool: price_reference.ReferencePool | None = None,
) -> dict:
    """把单条明细的历史价格校验结果整理为批次校验表格行。"""
    result = price_reference.check_price(
        db,
        product_name=item.product_name,
        unit_price=item.unit_price,
        currency=item.currency,
        tolerance=tolerance,
        only_confirmed=only_confirmed,
        exclude_batch_id=exclude_batch_id,
        pool=pool,
    )
    supplier = (source.supplier_name or "").strip() if source else ""
    return {
        "item_id": item.id,
        "supplier_name": supplier or "未命名供应商",
        "product_name": item.product_name,
        "spec": item.spec,
        "unit_price": item.unit_price,
        "currency": item.currency,
        "verdict": result["verdict"],
        "deviation_rate": result["deviation_rate"],
        "reference_avg": result["reference_avg"],
        "sample_count": result["sample_count"],
        "match_by": result["match_by"],
        "message": result["message"],
    }


@router.post("/items/{item_id}/price-check", response_model=PriceCheckResult)
def check_item_price(
    item_id: int,
    req: PriceCheckRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PriceCheckResult:
    """单条报价的合理性校验：与同币种历史均价比较（排除本批次自身样本）。"""
    item = db.get(QuoteItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "明细不存在")
    source = db.get(QuoteSource, item.source_id)
    unit_price = req.unit_price if req.unit_price is not None else item.unit_price
    result = price_reference.check_price(
        db,
        product_name=req.product_name or item.product_name,
        hs_code=req.hs_code,
        unit_price=unit_price,
        currency=req.currency or item.currency,
        tolerance=req.tolerance,
        only_confirmed=req.only_confirmed,
        exclude_batch_id=source.batch_id if source else None,
    )
    return PriceCheckResult(**result)


@router.post("/batches/{batch_id}/price-check", response_model=BatchPriceCheckResult)
def check_batch_prices(
    batch_id: int,
    req: BatchPriceCheckRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchPriceCheckResult:
    """批次级价格校验：逐条关联历史成交价，汇总偏低/合理/偏高/无参考数量。"""
    batch = db.get(QuoteBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "批次不存在")
    rows = (
        db.query(QuoteItem, QuoteSource)
        .join(QuoteSource, QuoteItem.source_id == QuoteSource.id)
        .filter(QuoteSource.batch_id == batch_id)
        .order_by(QuoteItem.id)
        .all()
    )
    counts = {"low": 0, "normal": 0, "high": 0, "no_reference": 0}
    # 历史价格池与要素索引只建一次，供全部明细复用（原实现每条明细各查一次全表）
    pool = price_reference.build_reference_pool(
        db, only_confirmed=req.only_confirmed, exclude_batch_id=batch_id
    )
    items: list[BatchPriceCheckItem] = []
    for item, source in rows:
        row = _price_check_row(
            db, item, source, req.tolerance, req.only_confirmed, batch_id, pool=pool
        )
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        items.append(BatchPriceCheckItem(**row))
    return BatchPriceCheckResult(
        batch_id=batch_id,
        tolerance=req.tolerance,
        total=len(rows),
        low=counts["low"],
        normal=counts["normal"],
        high=counts["high"],
        no_reference=counts["no_reference"],
        items=items,
    )