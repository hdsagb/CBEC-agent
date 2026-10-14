from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.report import (
    CategoryDistributionOut,
    SavingsOut,
    SupplierPriceTrendOut,
)
from app.services import reports

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/supplier-price-trend", response_model=SupplierPriceTrendOut)
def supplier_price_trend(
    months: int = Query(6, ge=1, le=36, description="统计最近几个自然月"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """供应商价格走势：按月份/供应商/币种聚合报价单价，用于观察报价波动。"""
    return reports.supplier_price_trend(db, months=months)


@router.get("/category-distribution", response_model=CategoryDistributionOut)
def category_distribution(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """报关品类分布：按 HS 章节聚合申报要素库，输出品类占比与覆盖客户数。"""
    return reports.category_distribution(db)


@router.get("/savings", response_model=SavingsOut)
def savings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """比价节省金额统计：按批次最新一次比价结果，汇总最优报价相对最高报价的节省。"""
    return reports.comparison_savings(db)