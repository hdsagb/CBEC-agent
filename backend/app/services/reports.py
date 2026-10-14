"""数据分析报表：供应商价格走势、报关品类分布、比价节省金额统计。

三个报表均直接基于既有业务表聚合，不额外落库：
- 价格走势：按「月份 + 供应商 + 币种」聚合报价明细的平均/最低/最高单价；
- 品类分布：按 HS 编码前两位（章节）聚合申报要素，输出占比与覆盖客户数；
- 节省金额：读取每个批次最新一次比价结果，用同币种内最高报价与最优报价的差额衡量节省。
"""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.declaration_element import DeclarationElement
from app.models.quote import Comparison, QuoteBatch, QuoteItem, QuoteSource

# HS 编码前两位 → 章节名称（常见章节，未收录的回退为「第 XX 章」）
HS_CHAPTER_LABELS: dict[str, str] = {
    "39": "塑料及其制品",
    "42": "皮革制品与箱包",
    "44": "木及木制品",
    "48": "纸及纸制品",
    "52": "棉及棉制品",
    "61": "针织服装",
    "62": "非针织服装",
    "63": "其他纺织制品",
    "64": "鞋靴",
    "70": "玻璃及玻璃制品",
    "72": "钢铁",
    "73": "钢铁制品",
    "76": "铝及其制品",
    "82": "工具与刀具",
    "83": "贱金属杂项制品",
    "84": "机械器具及零件",
    "85": "电机、电气设备",
    "87": "车辆及零件",
    "90": "光学、医疗仪器",
    "94": "家具与灯具",
    "95": "玩具与运动用品",
    "96": "杂项制品",
}

DEFAULT_CURRENCY = "CNY"


def _month_key(value: datetime | None) -> str:
    return (value or datetime.utcnow()).strftime("%Y-%m")


def _hs_chapter(hs_code: str) -> str:
    """取 HS 编码中的数字前两位作为章；不足两位时归入「00」。"""
    digits = "".join(ch for ch in (hs_code or "") if ch.isdigit())
    return digits[:2] if len(digits) >= 2 else "00"


def _chapter_label(chapter: str) -> str:
    if chapter == "00":
        return "未分类"
    return HS_CHAPTER_LABELS.get(chapter, f"第 {chapter} 章")


def supplier_price_trend(db: Session, months: int = 6) -> dict:
    """按月份/供应商/币种聚合已解析报价明细的单价，返回最近 N 个月的走势点。"""
    rows = (
        db.query(QuoteSource.supplier_name, QuoteSource.created_at, QuoteItem.unit_price, QuoteItem.currency)
        .join(QuoteItem, QuoteItem.source_id == QuoteSource.id)
        .filter(QuoteItem.unit_price.isnot(None))
        .all()
    )

    buckets: dict[tuple[str, str, str], list[float]] = {}
    for supplier, created_at, price, currency in rows:
        if price is None:
            continue
        name = (supplier or "").strip() or "未命名供应商"
        cur = (currency or DEFAULT_CURRENCY).strip() or DEFAULT_CURRENCY
        buckets.setdefault((_month_key(created_at), name, cur), []).append(float(price))

    all_months = sorted({month for month, _, _ in buckets})
    # months <= 0 视为不限制
    if months and months > 0 and len(all_months) > months:
        all_months = all_months[-months:]
    keep = set(all_months)

    points: list[dict] = []
    suppliers: set[str] = set()
    currencies: set[str] = set()
    for (month, name, cur), prices in buckets.items():
        if month not in keep:
            continue
        suppliers.add(name)
        currencies.add(cur)
        points.append(
            {
                "month": month,
                "supplier_name": name,
                "currency": cur,
                "avg_price": round(sum(prices) / len(prices), 4),
                "min_price": round(min(prices), 4),
                "max_price": round(max(prices), 4),
                "item_count": len(prices),
            }
        )
    points.sort(key=lambda p: (p["month"], p["supplier_name"], p["currency"]))

    return {
        "months": all_months,
        "suppliers": sorted(suppliers),
        "currencies": sorted(currencies),
        "points": points,
    }


def category_distribution(db: Session) -> dict:
    """按 HS 章节聚合申报要素库，输出品类占比与覆盖客户数。"""
    rows = db.query(DeclarationElement.hs_code, DeclarationElement.customer_name).all()

    counts: dict[str, int] = {}
    customers: dict[str, set[str]] = {}
    for hs_code, customer_name in rows:
        chapter = _hs_chapter(hs_code or "")
        counts[chapter] = counts.get(chapter, 0) + 1
        if (customer_name or "").strip():
            customers.setdefault(chapter, set()).add(customer_name.strip())

    total = sum(counts.values())
    slices = [
        {
            "hs_chapter": chapter,
            "label": _chapter_label(chapter),
            "element_count": count,
            "customer_count": len(customers.get(chapter, set())),
            "share": round(count / total, 4) if total else 0.0,
        }
        for chapter, count in counts.items()
    ]
    # 占比降序，其次章节号升序，保证展示稳定
    slices.sort(key=lambda s: (-s["element_count"], s["hs_chapter"]))

    return {"total_elements": total, "slices": slices}


def _latest_comparisons(db: Session) -> dict[int, Comparison]:
    """每个批次只保留最新一次比价结果，避免重复计算节省金额。"""
    out: dict[int, Comparison] = {}
    for comp in db.query(Comparison).order_by(Comparison.id).all():
        out[comp.batch_id] = comp
    return out


def comparison_savings(db: Session) -> dict:
    """统计比价节省金额：同币种内（最高报价 - 最优报价）× 数量口径为单件差额加总。"""
    comparisons = _latest_comparisons(db)
    batch_names = {b.id: b.name for b in db.query(QuoteBatch).all()}

    groups: list[dict] = []
    by_currency: dict[str, dict] = {}
    for batch_id, comp in comparisons.items():
        try:
            result = json.loads(comp.result_json or "[]")
        except (TypeError, ValueError):
            continue
        for group in result:
            candidates = group.get("candidates") or []
            priced = [c for c in candidates if c.get("unit_price") is not None]
            if len(priced) < 2:
                # 只有一家有效报价时无可比空间
                continue
            best = next((c for c in priced if c.get("is_best")), priced[0])
            currency = (best.get("currency") or DEFAULT_CURRENCY).strip() or DEFAULT_CURRENCY
            # 仅在最优供应商同币种内比较最高报价，避免混币种直接相减
            same_cur = [c for c in priced if ((c.get("currency") or DEFAULT_CURRENCY) == currency)]
            max_price = max(float(c["unit_price"]) for c in same_cur)
            best_price = float(best["unit_price"])
            saving = round(max_price - best_price, 4)
            if saving <= 0:
                continue
            groups.append(
                {
                    "batch_id": batch_id,
                    "batch_name": batch_names.get(batch_id, f"批次 {batch_id}"),
                    "product_name": group.get("product_name", ""),
                    "spec": group.get("spec", ""),
                    "currency": currency,
                    "best_supplier": best.get("supplier_name", ""),
                    "best_price": round(best_price, 4),
                    "max_price": round(max_price, 4),
                    "saving": saving,
                    "saving_rate": round(saving / max_price, 4) if max_price else 0.0,
                }
            )
            slot = by_currency.setdefault(currency, {"currency": currency, "total_savings": 0.0, "group_count": 0})
            slot["total_savings"] = round(slot["total_savings"] + saving, 4)
            slot["group_count"] += 1

    groups.sort(key=lambda g: (-g["saving"], g["batch_id"]))
    currency_list = sorted(by_currency.values(), key=lambda c: -c["total_savings"])

    return {
        # 汇总值为原币种直接相加，未做汇率折算，前端需显式提示口径
        "total_savings": round(sum(c["total_savings"] for c in currency_list), 4),
        "by_currency": currency_list,
        "batch_count": len(comparisons),
        "group_count": len(groups),
        "groups": groups,
    }