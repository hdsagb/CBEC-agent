import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.routers import agent, auth, elements, marks, quotes, reports, suppliers
from app.core.config import settings
from app.db import Base, SessionLocal, engine

logger = logging.getLogger("cbec")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动自检：JWT 密钥为示例值或过短时直接拒绝启动，避免上线后被伪造 token
    settings.validate_security()
    # 骨架阶段：启动时自动建表；后续迁移交给 alembic
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="CBEC Agent API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """给每个请求分配 ID 并回写响应头；未处理异常时把 ID 返回给前端，便于对照服务端日志。"""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("未处理异常 request_id=%s path=%s", request_id, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误", "request_id": request_id},
        )
    response.headers["X-Request-ID"] = request_id
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(elements.router)
app.include_router(quotes.router)
app.include_router(marks.router)
app.include_router(agent.router)
app.include_router(reports.router)
app.include_router(suppliers.router)

# 导出产物（箱唛 PDF/PNG 等）通过 /uploads 直链访问
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/api/health")
def health() -> JSONResponse:
    """健康检查真实探一次数据库，避免进程存活但数据库不可用时容器仍显示 healthy。"""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("健康检查失败：数据库不可用")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "app": "cbec-agent", "database": "unavailable"},
        )
    return JSONResponse(
        content={"status": "ok", "app": "cbec-agent", "version": "0.1.0", "database": "ok"}
    )

