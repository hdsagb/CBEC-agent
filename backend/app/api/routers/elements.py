from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db import get_db
from app.models.declaration_element import DeclarationElement
from app.models.user import User
from app.schemas.element import ElementCreate, ElementOut, ElementUpdate

router = APIRouter(prefix="/api/elements", tags=["elements"])


@router.get("", response_model=list[ElementOut])
def list_elements(
    keyword: str = Query("", description="产品名/客户名/HS编码 模糊搜索"),
    hs_code: str = Query(""),
    customer_name: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DeclarationElement]:
    q = db.query(DeclarationElement)
    if hs_code:
        q = q.filter(DeclarationElement.hs_code.contains(hs_code))
    if customer_name:
        q = q.filter(DeclarationElement.customer_name.contains(customer_name))
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                DeclarationElement.product_name.like(like),
                DeclarationElement.customer_name.like(like),
                DeclarationElement.hs_code.like(like),
                DeclarationElement.name_en.like(like),
            )
        )
    return q.order_by(DeclarationElement.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()


@router.get("/{element_id}", response_model=ElementOut)
def get_element(
    element_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeclarationElement:
    element = db.get(DeclarationElement, element_id)
    if element is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "要素记录不存在")
    return element


@router.post("", response_model=ElementOut)
def create_element(
    req: ElementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("customs")),
) -> DeclarationElement:
    element = DeclarationElement(**req.model_dump(), created_by=user.id, updated_by=user.id)
    db.add(element)
    db.commit()
    db.refresh(element)
    return element


@router.post("/{element_id}/copy", response_model=ElementOut)
def copy_element(
    element_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("customs")),
) -> DeclarationElement:
    """复制复用：以旧记录为底稿新建一条记录。"""
    src = db.get(DeclarationElement, element_id)
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "要素记录不存在")
    data = {c.name: getattr(src, c.name) for c in src.__table__.columns}
    for k in ("id", "version", "created_at", "updated_at"):
        data.pop(k, None)
    element = DeclarationElement(**data, created_by=user.id, updated_by=user.id)
    db.add(element)
    db.commit()
    db.refresh(element)
    return element


@router.put("/{element_id}", response_model=ElementOut)
def update_element(
    element_id: int,
    req: ElementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("customs")),
) -> DeclarationElement:
    element = db.get(DeclarationElement, element_id)
    if element is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "要素记录不存在")
    changes = req.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(element, k, v)
    element.updated_by = user.id
    db.commit()
    db.refresh(element)
    return element


@router.delete("/{element_id}")
def delete_element(
    element_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
) -> dict:
    element = db.get(DeclarationElement, element_id)
    if element is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "要素记录不存在")
    db.delete(element)
    db.commit()
    return {"ok": True}
