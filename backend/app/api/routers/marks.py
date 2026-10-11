from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models.mark import MarkJob, MarkTemplate
from app.models.user import User
from app.schemas.mark import MarkExportRequest, MarkJobCreate, MarkJobOut, MarkTemplateCreate, MarkTemplateOut
from app.services import mark_render

router = APIRouter(prefix="/api/marks", tags=["marks"])


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
    except mark_render.MarkFontMissingError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    return {
        "job_id": job_id,
        "format": fmt,
        "url": result["url"],
        "message": result["message"],
    }
