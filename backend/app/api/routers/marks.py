import io
import os
from types import SimpleNamespace

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models.mark import Asset, MarkJob, MarkTemplate
from app.models.user import User
from app.schemas.mark import (
    AssetOut,
    MarkExportRequest,
    MarkJobCreate,
    MarkJobOut,
    MarkPreviewRequest,
    MarkPreviewResult,
    MarkTemplateCreate,
    MarkTemplateOut,
    MarkTemplateUpdate,
)
from app.services import mark_render

router = APIRouter(prefix="/api/marks", tags=["marks"])

# 素材上传限制：仅图片，单文件不超过 5MB
ASSET_TYPES = {"logo", "qrcode", "barcode"}
ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
MAX_ASSET_BYTES = 5 * 1024 * 1024


def _render_error(exc: Exception) -> HTTPException:
    """渲染期异常统一转成 400（版式/素材问题属于请求侧错误）。"""
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/templates", response_model=list[MarkTemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MarkTemplate]:
    return db.query(MarkTemplate).order_by(MarkTemplate.created_at.desc()).all()


@router.post("/templates", response_model=MarkTemplateOut)
def create_template(
    req: MarkTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MarkTemplate:
    template = MarkTemplate(**req.model_dump(), created_by=user.id)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.put("/templates/{template_id}", response_model=MarkTemplateOut)
def update_template(
    template_id: int,
    req: MarkTemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MarkTemplate:
    """可视化编辑器保存：按需更新名称 / 版式，未提交的字段保持不变。"""
    template = db.get(MarkTemplate, template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "模板名称不能为空")
        template.name = name
    if req.layout_json is not None:
        template.layout_json = req.layout_json
    db.commit()
    db.refresh(template)
    return template


@router.get("/assets", response_model=list[AssetOut])
def list_assets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Asset]:
    return db.query(Asset).order_by(Asset.id.desc()).all()


@router.post("/assets", response_model=AssetOut)
async def upload_asset(
    file: UploadFile = File(...),
    type: str = Form("logo"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Asset:
    """上传箱唛素材（Logo 等图片），返回可被版式 ``src`` 引用的地址。"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ASSET_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"仅支持图片素材: {', '.join(sorted(ASSET_EXTENSIONS))}")
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "素材内容为空")
    if len(data) > MAX_ASSET_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"素材不能超过 {MAX_ASSET_BYTES // 1024 // 1024}MB")
    try:
        Image.open(io.BytesIO(data)).verify()  # 仅校验可解码，不保留句柄
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "素材不是可识别的图片文件") from exc

    asset = Asset(
        type=type if type in ASSET_TYPES else "logo",
        file_url=mark_render.save_asset_bytes(data, ext),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "素材不存在")
    local = mark_render.local_asset_path(asset.file_url)
    if local and os.path.isfile(local):
        try:
            os.remove(local)
        except OSError:  # 文件已被清理不应阻断记录删除
            pass
    db.delete(asset)
    db.commit()
    return {"deleted": asset_id}


@router.post("/preview", response_model=MarkPreviewResult)
def preview_layout(
    req: MarkPreviewRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """可视化编辑器预览：直接渲染提交的版式，返回单箱 300dpi PNG 地址。"""
    layout = mark_render.load_layout(req.layout_json)
    fields = mark_render.load_fields(req.fields_json)
    job = SimpleNamespace(order_no=req.order_no, total_boxes=req.total_boxes, start_no=req.start_no)
    try:
        return mark_render.export_preview(layout, job, fields, req.box_no)
    except (mark_render.MarkAssetMissingError, mark_render.MarkBarcodeError) as exc:
        raise _render_error(exc) from exc
    except mark_render.MarkFontMissingError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc


@router.post("/jobs", response_model=MarkJobOut)
def create_job(
    req: MarkJobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MarkJob:
    if db.get(MarkTemplate, req.template_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    job = MarkJob(**req.model_dump(), created_by=user.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[MarkJobOut])
def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MarkJob]:
    return db.query(MarkJob).order_by(MarkJob.created_at.desc()).all()


@router.post("/jobs/{job_id}/export")
def export_job(
    job_id: int,
    req: MarkExportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """导出 300dpi 箱唛：PDF 一箱一页，PNG 多箱竖向拼接。"""
    job = db.get(MarkJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    template = db.get(MarkTemplate, job.template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    fmt = (req.format or "pdf").lower()
    if fmt not in ("pdf", "png"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不支持的导出格式: {req.format}")
    try:
        result = mark_render.export_box_mark(job, template, fmt)
    except (mark_render.MarkAssetMissingError, mark_render.MarkBarcodeError) as exc:
        raise _render_error(exc) from exc
    except mark_render.MarkFontMissingError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    return {
        "job_id": job_id,
        "format": fmt,
        "url": result["url"],
        "message": result["message"],
    }
