from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import agent, auth, elements, marks, quotes
from app.core.config import settings
from app.db import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 骨架阶段：启动时自动建表；后续迁移交给 alembic
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="CBEC Agent API", version="0.1.0", lifespan=lifespan)

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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": "cbec-agent", "version": "0.1.0"}
