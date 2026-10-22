from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db import get_db
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.supplier import (
    SupplierCreate,
    SupplierOut,
    SupplierPage,
    SupplierQuotePage,
    SupplierQuoteStatPage,
    SupplierUpdate,
)
from app.services import suppliers as supplier_service

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


def _check_status(value: str) -> str:
    if value not in supplier_service.SUPPLIER_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"供应商状态不合法，可选值：{'/'.join(sorted(supplier_service.SUPPLIER_STATUSES))}",
        )
    return value


@router.get("", response_model=SupplierPage)
def list_suppliers(
    keyword: str = Query("", description="名称/地区/主营品类/联系人 模糊搜索"),
    status_filter: str = Query("", alias="status", description="active|paused|blacklisted"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SupplierPage:
    q = db.query(Supplier)
    if status_filter:
        # 非法状态直接报错，避免静默返回空列表让前端误以为是「没有数据」
        q = q.filter(Supplier.status == _check_status(status_filter))
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                Supplier.name.like(like),
                Supplier.region.like(like),
                Supplier.main_category.like(like),
                Supplier.contact_name.like(like),
            )
        )
    total = q.count()
    items = (
        q.order_by(Supplier.updated_at.desc(), Supplier.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return SupplierPage(items=items, total=total, page=page, page_size=page_size)


# 注意：以下固定路径必须注册在 /{supplier_id} 之前，否则会被当作 id 匹配。
@router.get("/currencies", response_model=list[str])
def list_currencies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[str]:
    """历史报价中出现过的币种，供筛选下拉使用。"""
    return supplier_service.quote_currencies(db)


@router.get("/quote-stats", response_model=SupplierQuoteStatPage)
def quote_stats(
    keyword: str = Query("", description="供应商名称模糊搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SupplierQuoteStatPage:
    """历史报价库概览：按供应商名称聚合报价次数、覆盖品类、最近报价时间。"""
    stats = supplier_service.supplier_quote_stats(db, keyword=keyword)
    start = (page - 1) * page_size
    return SupplierQuoteStatPage(
        items=stats[start : start + page_size],
        total=len(stats),
        page=page,
        page_size=page_size,
    )


@router.get("/quotes", response_model=SupplierQuotePage)
def search_quotes(
    keyword: str = Query("", description="商品名/规格/供应商名 模糊搜索"),
    supplier_name: str = Query(""),
    currency: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SupplierQuotePage:
    """全局历史报价检索：跨批次查看某商品/供应商的历史报价记录。"""
    items, total = supplier_service.quote_items_page(
        db,
        keyword=keyword,
        supplier_name=supplier_name,
        currency=currency,
        page=page,
        page_size=page_size,
    )
    return SupplierQuotePage(items=items, total=total, page=page, page_size=page_size)


def _get_or_404(db: Session, supplier_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "供应商档案不存在")
    return supplier


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Supplier:
    return _get_or_404(db, supplier_id)


@router.get("/{supplier_id}/quotes", response_model=SupplierQuotePage)
def list_supplier_quotes(
    supplier_id: int,
    keyword: str = Query("", description="商品名/规格 模糊搜索"),
    currency: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SupplierQuotePage:
    """某供应商的历史报价明细（按名称匹配报价来源）。"""
    supplier = _get_or_404(db, supplier_id)
    items, total = supplier_service.quote_items_page(
        db,
        keyword=keyword,
        supplier_name=supplier.name,
        currency=currency,
        page=page,
        page_size=page_size,
    )
    return SupplierQuotePage(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=SupplierOut)
def create_supplier(
    req: SupplierCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("customs")),
) -> Supplier:
    name = req.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "供应商名称不能为空")
    _check_status(req.status)
    if db.query(Supplier).filter(Supplier.name == name).first() is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "供应商名称已存在")
    payload = req.model_dump()
    payload["name"] = name
    supplier = Supplier(**payload, created_by=user.id)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int,
    req: SupplierUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("customs")),
) -> Supplier:
    supplier = _get_or_404(db, supplier_id)
    changes = req.model_dump(exclude_unset=True)
    if "name" in changes:
        name = (changes["name"] or "").strip()
        if not name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "供应商名称不能为空")
        exists = (
            db.query(Supplier)
            .filter(Supplier.name == name, Supplier.id != supplier_id)
            .first()
        )
        if exists is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "供应商名称已存在")
        changes["name"] = name
    if "status" in changes:
        _check_status(changes["status"])
    for key, value in changes.items():
        setattr(supplier, key, value)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
) -> dict:
    """删除档案：若该供应商已有历史报价，拒绝删除并建议改为「暂停合作」。"""
    supplier = _get_or_404(db, supplier_id)
    if supplier_service.supplier_quote_count(db, supplier.name) > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "该供应商已存在历史报价记录，删除会中断报价溯源，建议将其状态改为「暂停合作」",
        )
    db.delete(supplier)
    db.commit()
    return {"ok": True}