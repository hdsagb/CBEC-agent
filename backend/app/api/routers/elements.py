import json
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db import get_db
from app.models.declaration_element import DeclarationElement
from app.models.user import User
from app.schemas.element import (
    DeclarationText,
    ElementCreate,
    ElementImportResult,
    ElementOut,
    ElementPage,
    ElementUpdate,
)
from app.schemas.price_reference import PriceReference
from app.services import element_excel, element_import, price_reference

router = APIRouter(prefix="/api/elements", tags=["elements"])

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_IMPORT_ERROR_LIMIT = 20

# 报关格式文本的字段顺序与中文标签
_TEXT_FIELDS: list[tuple[str, str]] = [
    ("hs_code", "HS编码"),
    ("product_name", "商品名称"),
    ("name_en", "英文名称"),
    ("customer_name", "客户名称"),
    ("brand", "品牌"),
    ("model", "型号"),
    ("spec", "规格"),
    ("material", "材质"),
    ("usage", "用途"),
]


def _parse_extra(elements_json: str) -> list[dict]:
    try:
        data = json.loads(elements_json or "[]")
    except (ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []


def _build_declaration_text(element: DeclarationElement) -> str:
    """把要素记录拼成可直接粘贴到报关单的文本。"""
    lines: list[str] = []
    for field, label in _TEXT_FIELDS:
        value = str(getattr(element, field, "") or "").strip()
        if value:
            lines.append(f"{label}：{value}")
    extra = _parse_extra(element.elements_json)
    extra_lines = []
    for item in extra:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "") or "").strip()
        value = str(item.get("value", "") or "").strip()
        if name or value:
            extra_lines.append(f"  {name}：{value}")
    if extra_lines:
        lines.append("其它要素：")
        lines.extend(extra_lines)
    return "\n".join(lines)


def _xlsx_response(data: bytes, filename: str) -> Response:
    """构造 xlsx 下载响应：文件名按 RFC 5987 编码，另附 ASCII 兜底名。"""
    return Response(
        content=data,
        media_type=_XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"elements.xlsx\"; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


def _base_query(db: Session, keyword: str, hs_code: str, customer_name: str):
    """列表 / 导出共用的筛选条件。"""
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
    return q


@router.get("", response_model=ElementPage)
def list_elements(
    keyword: str = Query("", description="产品名/客户名/HS编码 模糊搜索"),
    hs_code: str = Query(""),
    customer_name: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ElementPage:
    q = _base_query(db, keyword, hs_code, customer_name)
    total = q.count()
    items = (
        q.order_by(DeclarationElement.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ElementPage(items=items, total=total, page=page, page_size=page_size)


# 注意：以下两条固定路径必须注册在 /{element_id} 之前，否则会被当作 id 匹配。
@router.get("/template")
def download_template(
    user: User = Depends(require_role("customs")),
) -> Response:
    """下载空白导入模板（仅表头）。"""
    return _xlsx_response(element_excel.build_workbook([]), "申报要素导入模板.xlsx")


@router.get("/export")
def export_elements(
    keyword: str = Query(""),
    hs_code: str = Query(""),
    customer_name: str = Query(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """按当前筛选条件导出全部匹配记录为 xlsx。"""
    elements = (
        _base_query(db, keyword, hs_code, customer_name)
        .order_by(DeclarationElement.updated_at.desc())
        .all()
    )
    filename = f"申报要素_{datetime.now():%Y%m%d_%H%M}.xlsx"
    return _xlsx_response(element_excel.build_workbook(elements), filename)


@router.post("/import", response_model=ElementImportResult)
async def import_elements(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("customs")),
) -> ElementImportResult:
    """批量导入：按「HS编码 + 商品名称 + 客户名称」去重，重复行跳过不覆盖。"""
    filename = file.filename or ""
    if not filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 .xlsx 文件，请先另存为 xlsx")
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件内容为空")
    try:
        records, errors = element_excel.parse_workbook(data)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "文件解析失败，请确认是有效的 Excel 文件"
        ) from exc

    stats = element_import.bulk_import(db, records, user.id)

    return ElementImportResult(
        total=len(records) + len(errors),
        created=stats["created"],
        skipped=stats["skipped"],
        invalid=len(errors) + stats["invalid"],
        errors=(errors + stats["errors"])[:_IMPORT_ERROR_LIMIT],
    )


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


@router.get("/{element_id}/declaration-text", response_model=DeclarationText)
def get_declaration_text(
    element_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeclarationText:
    """一键复制：生成报关格式文本。"""
    element = db.get(DeclarationElement, element_id)
    if element is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "要素记录不存在")
    return DeclarationText(text=_build_declaration_text(element))


@router.get("/{element_id}/price-reference", response_model=PriceReference)
def get_price_reference(
    element_id: int,
    only_confirmed: bool = Query(True, description="是否仅取已确认的历史报价"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PriceReference:
    """按该要素的 HS 编码／商品名关联历史成交价，用于报价合理性参考。"""
    element = db.get(DeclarationElement, element_id)
    if element is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "要素记录不存在")
    return PriceReference(
        **price_reference.price_reference(
            db,
            hs_code=element.hs_code,
            product_name=element.product_name,
            only_confirmed=only_confirmed,
        )
    )


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
    for k in ("id", "version", "created_at", "updated_at", "created_by", "updated_by"):
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
