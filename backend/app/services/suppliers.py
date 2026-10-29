"""供应商主数据与历史报价库的服务层。

历史报价直接基于既有业务表（quote_source / quote_item / quote_batch）聚合，
不额外落库：供应商档案通过 supplier_name 字符串与报价记录关联，便于按供应商
汇总「报价次数、覆盖品类、最近报价时间」等长期决策指标。
"""

from sqlalchemy import distinct, func, or_
from sqlalchemy.orm import Session

from app.models.quote import QuoteBatch, QuoteItem, QuoteSource
from app.models.supplier import Supplier

UNKNOWN_SUPPLIER = "未命名供应商"
DEFAULT_CURRENCY = "CNY"

# 主数据状态取值，用于接口校验
SUPPLIER_STATUSES = {"active", "paused", "blacklisted"}


def _supplier_key():
    """供应商归档名：去掉首尾空格，空名称统一归入「未命名供应商」。"""
    return func.coalesce(func.nullif(func.trim(QuoteSource.supplier_name), ""), UNKNOWN_SUPPLIER)


def _currency_key():
    """币种归档名：空值统一按默认币种统计，避免同一供应商拆成两档。"""
    return func.coalesce(func.nullif(func.trim(QuoteItem.currency), ""), DEFAULT_CURRENCY)


def _history_query(db: Session):
    """历史报价明细的基础查询（报价来源 → 明细）。"""
    return db.query(QuoteSource).join(QuoteItem, QuoteItem.source_id == QuoteSource.id)


def supplier_quote_stats(
    db: Session,
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """按供应商名称聚合历史报价概览，并回填已建档供应商的主数据信息。

    聚合与分页均在数据库侧完成（GROUP BY + LIMIT/OFFSET），避免全表加载到内存。
    返回 (当前页数据, 供应商总数)，按报价明细条数降序、名称升序排列。
    """
    name_col = _supplier_key()
    q = _history_query(db)
    kw = keyword.strip()
    if kw:
        q = q.filter(name_col.like(f"%{kw}%"))

    total = q.with_entities(func.count(distinct(name_col))).scalar() or 0
    if total == 0:
        return [], 0

    agg_rows = (
        q.with_entities(
            name_col.label("supplier_name"),
            func.count(QuoteItem.id).label("item_count"),
            func.count(QuoteItem.unit_price).label("priced_count"),
            func.count(distinct(QuoteSource.batch_id)).label("batch_count"),
            func.count(distinct(func.nullif(func.trim(QuoteItem.product_name), ""))).label(
                "product_count"
            ),
            func.max(QuoteSource.created_at).label("last_quote_at"),
        )
        .group_by(name_col)
        .order_by(func.count(QuoteItem.id).desc(), name_col)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    if not agg_rows:
        return [], total

    names = [row.supplier_name for row in agg_rows]

    currency_col = _currency_key()
    price_rows = (
        db.query(
            name_col.label("supplier_name"),
            currency_col.label("currency"),
            func.count(QuoteItem.id).label("item_count"),
            func.avg(QuoteItem.unit_price).label("avg_price"),
            func.min(QuoteItem.unit_price).label("min_price"),
            func.max(QuoteItem.unit_price).label("max_price"),
        )
        .join(QuoteItem, QuoteItem.source_id == QuoteSource.id)
        .filter(name_col.in_(names), QuoteItem.unit_price.isnot(None))
        .group_by(name_col, currency_col)
        .order_by(name_col, currency_col)
        .all()
    )
    price_stats: dict[str, list[dict]] = {}
    for row in price_rows:
        price_stats.setdefault(row.supplier_name, []).append(
            {
                "currency": row.currency,
                "item_count": row.item_count,
                "avg_price": round(float(row.avg_price), 4),
                "min_price": round(float(row.min_price), 4),
                "max_price": round(float(row.max_price), 4),
            }
        )

    profiles = {
        supplier.name: supplier
        for supplier in db.query(Supplier).filter(Supplier.name.in_(names)).all()
    }

    items: list[dict] = []
    for row in agg_rows:
        profile = profiles.get(row.supplier_name)
        stats = price_stats.get(row.supplier_name, [])
        items.append(
            {
                "supplier_name": row.supplier_name,
                "item_count": row.item_count,
                "priced_count": row.priced_count,
                "batch_count": row.batch_count,
                "product_count": row.product_count,
                "currencies": [stat["currency"] for stat in stats],
                "last_quote_at": row.last_quote_at,
                "price_stats": stats,
                "supplier_id": profile.id if profile else None,
                "status": profile.status if profile else "",
                "rating": profile.rating if profile else 0.0,
                "region": profile.region if profile else "",
            }
        )
    return items, total


def _quote_query(db: Session, keyword: str, supplier_name: str, currency: str):
    """历史报价明细的公共筛选条件。"""
    q = (
        db.query(QuoteItem, QuoteSource, QuoteBatch)
        .join(QuoteSource, QuoteItem.source_id == QuoteSource.id)
        .join(QuoteBatch, QuoteSource.batch_id == QuoteBatch.id)
    )
    if supplier_name:
        q = q.filter(QuoteSource.supplier_name == supplier_name)
    if currency:
        q = q.filter(QuoteItem.currency == currency)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                QuoteItem.product_name.like(like),
                QuoteItem.spec.like(like),
                QuoteSource.supplier_name.like(like),
            )
        )
    return q


def quote_items_page(
    db: Session,
    keyword: str = "",
    supplier_name: str = "",
    currency: str = "",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """历史报价明细分页检索：支持按商品/规格/供应商关键词、供应商、币种筛选。"""
    q = _quote_query(db, keyword, supplier_name, currency)
    total = q.count()
    rows = (
        q.order_by(QuoteItem.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": item.id,
            "supplier_name": (source.supplier_name or "").strip() or UNKNOWN_SUPPLIER,
            "batch_id": source.batch_id,
            "batch_name": batch.name,
            "product_name": item.product_name,
            "spec": item.spec,
            "unit_price": item.unit_price,
            "currency": item.currency,
            "moq": item.moq,
            "lead_time_days": item.lead_time_days,
            "confirmed": item.confirmed,
            "quote_time": source.created_at,
        }
        for item, source, batch in rows
    ]
    return items, total


def quote_currencies(db: Session) -> list[str]:
    """历史报价中出现过的币种，供前端筛选下拉使用。"""
    rows = db.query(QuoteItem.currency).distinct().all()
    values = {(c or "").strip() for (c,) in rows if (c or "").strip()}
    return sorted(values)


def supplier_quote_count(db: Session, supplier_name: str) -> int:
    """统计某供应商名称下的历史报价明细条数，用于删除档案前的占用校验。"""
    return (
        db.query(QuoteItem)
        .join(QuoteSource, QuoteItem.source_id == QuoteSource.id)
        .filter(QuoteSource.supplier_name == supplier_name)
        .count()
    )