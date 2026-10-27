"""要素与比价联动：按 HS 编码关联历史成交价，反哺报价合理性校验。

不额外落库，直接复用既有业务表：
- 要素库 declaration_element 提供「商品名 ↔ HS 编码」映射，用于把历史报价归因到 HS 编码；
- 报价明细 quote_item（默认仅取已确认）构成历史价格池；
- 校验时先按归一化商品名精确匹配，命中不足时回退到同 HS 编码的同类商品。
"""

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.declaration_element import DeclarationElement
from app.models.quote import QuoteBatch, QuoteItem, QuoteSource

UNKNOWN_SUPPLIER = "未命名供应商"
DEFAULT_CURRENCY = "CNY"
DEFAULT_TOLERANCE = 0.2
DEFAULT_SAMPLE_LIMIT = 10

# 归一化时剔除的字符：空白与常见中英文标点
_PUNCT_RE = re.compile(r"[\s\-_/\\·、,，.。;；:：'\"“”‘’()（）\[\]【】{}<>+*&]+")


def normalize_name(value: str) -> str:
    """商品名归一化：去空白/标点并转小写，用于跨书写差异的精确匹配。"""
    return _PUNCT_RE.sub("", (value or "").strip().lower())


def _norm_hs(value: str) -> str:
    """HS 编码归一化：仅保留数字，兼容 8517.62 与 851762 两种写法。"""
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _element_index(db: Session) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """由要素库构建双向索引：商品名归一化 → HS 编码集合，及其反向映射。"""
    name_to_hs: dict[str, set[str]] = {}
    hs_to_names: dict[str, set[str]] = {}
    rows = db.query(DeclarationElement.product_name, DeclarationElement.hs_code).all()
    for product_name, hs_code in rows:
        key = normalize_name(product_name)
        hs = _norm_hs(hs_code)
        if not key or not hs:
            continue
        name_to_hs.setdefault(key, set()).add(hs)
        hs_to_names.setdefault(hs, set()).add(key)
    return name_to_hs, hs_to_names


def _quote_rows(
    db: Session, only_confirmed: bool, exclude_batch_id: int | None
) -> list[tuple[QuoteItem, QuoteSource, QuoteBatch]]:
    """历史价格池：报价明细 + 来源 + 批次，可按确认状态过滤、排除指定批次。"""
    q = (
        db.query(QuoteItem, QuoteSource, QuoteBatch)
        .join(QuoteSource, QuoteItem.source_id == QuoteSource.id)
        .join(QuoteBatch, QuoteSource.batch_id == QuoteBatch.id)
    )
    if only_confirmed:
        q = q.filter(QuoteItem.confirmed.is_(True))
    if exclude_batch_id is not None:
        q = q.filter(QuoteSource.batch_id != exclude_batch_id)
    return q.all()


@dataclass
class ReferencePool:
    """一次请求内可复用的历史参考数据池。

    批次级校验会对每条明细各算一次参考价，若每次都重新拉全表并归一化商品名，
    开销是「明细数 × 历史报价数」。把历史池与商品名索引建一次即可把重复部分摊薄。
    """

    name_to_hs: dict[str, set[str]]
    hs_to_names: dict[str, set[str]]
    # 归一化商品名 → 该商品的全部历史报价行
    by_name: dict[str, list[tuple[QuoteItem, QuoteSource, QuoteBatch]]]


def build_reference_pool(
    db: Session,
    only_confirmed: bool = True,
    exclude_batch_id: int | None = None,
) -> ReferencePool:
    """构建参考数据池：要素索引 + 历史报价按归一化商品名分组。"""
    name_to_hs, hs_to_names = _element_index(db)
    by_name: dict[str, list[tuple[QuoteItem, QuoteSource, QuoteBatch]]] = {}
    for item, source, batch in _quote_rows(db, only_confirmed, exclude_batch_id):
        key = normalize_name(item.product_name)
        if not key:
            continue
        by_name.setdefault(key, []).append((item, source, batch))
    return ReferencePool(name_to_hs=name_to_hs, hs_to_names=hs_to_names, by_name=by_name)


def price_reference(
    db: Session,
    hs_code: str = "",
    product_name: str = "",
    only_confirmed: bool = True,
    exclude_batch_id: int | None = None,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
    pool: ReferencePool | None = None,
) -> dict:
    """按 HS 编码 + 商品名检索历史成交价。

    匹配顺序：归一化商品名精确匹配（match_by=product）→ 同 HS 编码同类商品兜底
    （match_by=hs_code）→ 无参考（match_by=none）。统计按币种分组，避免跨币种平均。

    批量校验时传入同一个 ``pool`` 可复用历史池与索引，避免每条明细重复全表查询。
    """
    norm_query = normalize_name(product_name)
    if pool is None:
        pool = build_reference_pool(db, only_confirmed, exclude_batch_id)
    name_to_hs, hs_to_names, by_name = pool.name_to_hs, pool.hs_to_names, pool.by_name

    target_hs = _norm_hs(hs_code)
    if not target_hs and norm_query:
        candidates = sorted(name_to_hs.get(norm_query, set()))
        target_hs = candidates[0] if candidates else ""

    matched: list[tuple[QuoteItem, QuoteSource, QuoteBatch]] = []
    match_by = "none"
    if norm_query:
        matched = list(by_name.get(norm_query, []))
        if matched:
            match_by = "product"
    if not matched and target_hs:
        for name in hs_to_names.get(target_hs, set()):
            matched.extend(by_name.get(name, []))
        if matched:
            match_by = "hs_code"

    priced = [r for r in matched if r[0].unit_price is not None]

    buckets: dict[str, list[tuple[float, datetime | None, QuoteItem, QuoteSource]]] = {}
    for item, source, _batch in priced:
        cur = (item.currency or DEFAULT_CURRENCY).strip() or DEFAULT_CURRENCY
        buckets.setdefault(cur, []).append((float(item.unit_price), source.created_at, item, source))

    currency_stats: list[dict] = []
    for cur in sorted(buckets):
        entries = buckets[cur]
        prices = [e[0] for e in entries]
        latest = max(entries, key=lambda e: e[1] or datetime.min)
        currency_stats.append(
            {
                "currency": cur,
                "item_count": len(prices),
                "avg_price": round(sum(prices) / len(prices), 4),
                "min_price": round(min(prices), 4),
                "max_price": round(max(prices), 4),
                "last_price": round(latest[0], 4),
                "last_quote_at": latest[1],
            }
        )

    recent = sorted(priced, key=lambda r: r[1].created_at or datetime.min, reverse=True)[:sample_limit]
    samples = [
        {
            "quote_item_id": item.id,
            "supplier_name": (source.supplier_name or "").strip() or UNKNOWN_SUPPLIER,
            "product_name": item.product_name,
            "spec": item.spec,
            "unit_price": item.unit_price,
            "currency": item.currency,
            "batch_id": batch.id,
            "batch_name": batch.name,
            "quote_time": source.created_at,
        }
        for item, source, batch in recent
    ]

    return {
        "hs_code": target_hs,
        "product_name": product_name,
        "match_by": match_by,
        "sample_count": len(priced),
        "currency_stats": currency_stats,
        "samples": samples,
    }


def check_price(
    db: Session,
    product_name: str = "",
    hs_code: str = "",
    unit_price: float | None = None,
    currency: str = DEFAULT_CURRENCY,
    tolerance: float = DEFAULT_TOLERANCE,
    only_confirmed: bool = True,
    exclude_batch_id: int | None = None,
    pool: ReferencePool | None = None,
) -> dict:
    """单条报价的合理性校验：与同币种历史均价比较，给出偏低/合理/偏高判定。"""
    ref = price_reference(
        db,
        hs_code=hs_code,
        product_name=product_name,
        only_confirmed=only_confirmed,
        exclude_batch_id=exclude_batch_id,
        pool=pool,
    )
    cur = (currency or DEFAULT_CURRENCY).strip() or DEFAULT_CURRENCY
    stat = next((s for s in ref["currency_stats"] if s["currency"] == cur), None)

    result: dict = {
        "verdict": "no_reference",
        "unit_price": unit_price,
        "currency": cur,
        "deviation_rate": None,
        "tolerance": tolerance,
        "reference_avg": stat["avg_price"] if stat else None,
        "reference_min": stat["min_price"] if stat else None,
        "reference_max": stat["max_price"] if stat else None,
        "sample_count": stat["item_count"] if stat else 0,
        "match_by": ref["match_by"],
        "hs_code": ref["hs_code"],
        "message": "",
    }

    if unit_price is None:
        result["message"] = "该明细暂无单价，无法校验"
        return result
    if stat is None:
        if ref["match_by"] == "none":
            result["message"] = "暂无历史参考价，无法判断合理性"
        else:
            result["message"] = f"历史参考价中暂无 {cur} 币种样本，无法判断合理性"
        return result

    avg = stat["avg_price"]
    rate = (float(unit_price) - avg) / avg if avg else 0.0
    result["deviation_rate"] = round(rate, 4)

    if float(unit_price) < avg * (1 - tolerance):
        result["verdict"] = "low"
        result["message"] = (
            f"低于历史均价 {abs(rate) * 100:.1f}%（参考 {cur} {avg}），建议核实成本与品质"
        )
    elif float(unit_price) > avg * (1 + tolerance):
        result["verdict"] = "high"
        result["message"] = (
            f"高于历史均价 {rate * 100:.1f}%（参考 {cur} {avg}），建议重新议价"
        )
    else:
        result["verdict"] = "normal"
        result["message"] = (
            f"与历史均价偏差 {rate * 100:.1f}%，处于合理区间（参考 {cur} {avg}）"
        )
    return result