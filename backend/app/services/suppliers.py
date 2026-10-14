"""供应商主数据与历史报价库的服务层。

历史报价直接基于既有业务表（quote_source / quote_item / quote_batch）聚合，
不额外落库：供应商档案通过 supplier_name 字符串与报价记录关联，便于按供应商
汇总「报价次数、覆盖品类、最近报价时间」等长期决策指标。
"""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.quote import QuoteBatch, QuoteItem, QuoteSource
from app.models.supplier import Supplier

UNKNOWN_SUPPLIER = "未命名供应商"
DEFAULT_CURRENCY = "CNY"

# 主数据状态取值，用于接口校验
SUPPLIER_STATUSES = {"active", "paused", "blacklisted"}


def _price_stat(buckets: dict[str, list[float]]) -> list[dict]:
    """把「币种 → 价格列表」整理为按币种的统计列表。"""
    out: list[dict] = []
    for currency in sorted(buckets):
        prices = buckets[currency]
        if not prices:
            continue
        out.append(
            {
                "currency": currency,
                "item_count": len(prices),
                "avg_price": round(sum(prices) / len(prices), 4),
                "min_price": round(min(prices), 4),
                "max_price": round(max(prices), 4),
            }
        )
    return out


def supplier_quote_stats(db: Session, keyword: str = "") -> list[dict]:
    """按供应商名称聚合历史报价概览，并回填已建档供应商的主数据信息。

    返回结果按报价明细条数降序、名称升序排列，供前端分页展示。
    """
    rows = (
        db.query(
            QuoteSource.supplier_name,
            QuoteSource.batch_id,
            QuoteSource.created_at,
            QuoteItem.product_name,
            QuoteItem.unit_price,
            QuoteItem.currency,
        )
        .join(QuoteItem, QuoteItem.source_id == QuoteSource.id)
        .all()
    )

    agg: dict[str, dict] = {}
    for name, batch_id, created_at, product_name, price, currency in rows:
        key = (name or "").strip() or UNKNOWN_SUPPLIER
        slot = agg.setdefault(
            key,
            {
                "supplier_name": key,
                "item_count": 0,
                "priced_count": 0,
                "batches": set(),
                "products": set(),
                "currencies": set(),
                "last_quote_at": None,
                "price_buckets": {},
            },
        )
        slot["item_count"] += 1
        slot["batches"].add(batch_id)
        if (product_name or "").strip():
            slot["products"].add(product_name.strip())
        if created_at and (slot["last_quote_at"] is None or created_at > slot["last_quote_at"]):
            slot["last_quote_at"] = created_at
        if price is None:
            continue
        slot["priced_count"] += 1
        cur = (currency or DEFAULT_CURRENCY).strip() or DEFAULT_CURRENCY
        slot["currencies"].add(cur)
        slot["price_buckets"].setdefault(cur, []).append(float(price))

    kw = keyword.strip()
    if kw:
        agg = {name: slot for name, slot in agg.items() if kw in name}

    profiles = {s.name: s for s in db.query(Supplier).all()}

    out: list[dict] = []
    for name, slot in agg.items():
        profile = profiles.get(name)
        out.append(
            {
                "supplier_name": name,
                "item_count": slot["item_count"],
                "priced_count": slot["priced_count"],
                "batch_count": len(slot["batches"]),
                "product_count": len(slot["products"]),
                "currencies": sorted(slot["currencies"]),
                "last_quote_at": slot["last_quote_at"],
                "price_stats": _price_stat(slot["price_buckets"]),
                "supplier_id": profile.id if profile else None,
                "status": profile.status if profile else "",
                "rating": profile.rating if profile else 0.0,
                "region": profile.region if profile else "",
            }
        )
    out.sort(key=lambda s: (-s["item_count"], s["supplier_name"]))
    return out


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