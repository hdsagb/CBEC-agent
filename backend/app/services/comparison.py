"""智能比价引擎：四维（价格 / MOQ / 货期 / 置信度）归一化 + 加权打分。

按「商品（名称+规格）」聚合已确认明细，同一商品横向对比各供应商报价，
输出每个候选的四维得分、加权总分与最优供应商推荐。权重可配置且落库。
"""

import json

from sqlalchemy.orm import Session

from app.models.quote import Comparison, QuoteBatch, QuoteItem, QuoteSource

DEFAULT_WEIGHTS: dict[str, float] = {
    "price": 0.5,
    "moq": 0.2,
    "lead_time": 0.2,
    "confidence": 0.1,
}

# 数值越小越优的维度
LOWER_BETTER = {"price", "moq", "lead_time"}


def normalize_weights(weight_config: dict | None) -> dict[str, float]:
    """过滤非法维度与负权重，并归一化到和为 1。空配置回退默认权重。"""
    cfg: dict[str, float] = {}
    for key, value in (weight_config or {}).items():
        if key not in DEFAULT_WEIGHTS:
            continue
        try:
            num = float(value)
        except (TypeError, ValueError):
            continue
        if num > 0:
            cfg[key] = num
    if not cfg:
        cfg = dict(DEFAULT_WEIGHTS)
    for key in DEFAULT_WEIGHTS:
        cfg.setdefault(key, 0.0)
    total = sum(cfg.values()) or 1.0
    return {key: round(cfg[key] / total, 6) for key in DEFAULT_WEIGHTS}


def _product_key(name: str | None, spec: str | None) -> str:
    return f"{(name or '').strip().lower()}|{(spec or '').strip().lower()}"


def _dim_value(item: QuoteItem, dim: str):
    if dim == "price":
        return item.unit_price
    if dim == "moq":
        return item.moq
    if dim == "lead_time":
        return item.lead_time_days
    if dim == "confidence":
        return item.confidence
    return None


def _normalize(pairs: list[tuple[int, float | None]], lower_better: bool) -> dict[int, float]:
    """min-max 归一化；缺值按最差（0）处理，全部相等时统一给 1。"""
    present = [v for _, v in pairs if v is not None]
    if not present:
        return {i: 0.0 for i, _ in pairs}
    lo, hi = min(present), max(present)
    out: dict[int, float] = {}
    for i, v in pairs:
        if v is None:
            out[i] = 0.0
        elif hi == lo:
            out[i] = 1.0
        elif lower_better:
            out[i] = (hi - v) / (hi - lo)
        else:
            out[i] = (v - lo) / (hi - lo)
    return out


def _candidate(
    item: QuoteItem,
    supplier: str,
    scores: dict[str, float],
    total: float,
) -> dict:
    return {
        "item_id": item.id,
        "source_id": item.source_id,
        "supplier_name": supplier,
        "product_name": item.product_name,
        "spec": item.spec,
        "unit_price": item.unit_price,
        "currency": item.currency,
        "moq": item.moq,
        "lead_time_days": item.lead_time_days,
        "confidence": round(item.confidence, 4),
        "scores": scores,
        "total_score": total,
        "is_best": False,
    }


def compare_batch(
    db: Session,
    batch_id: int,
    weight_config: dict | None = None,
    persist: bool = True,
) -> dict:
    """执行比价：聚合 → 四维归一化 → 加权排序 → 落库。返回结果字典。"""
    batch = db.get(QuoteBatch, batch_id)
    if batch is None:
        raise ValueError("批次不存在")

    items = (
        db.query(QuoteItem)
        .join(QuoteSource, QuoteItem.source_id == QuoteSource.id)
        .filter(QuoteSource.batch_id == batch_id, QuoteItem.confirmed.is_(True))
        .all()
    )
    supplier_map = {
        s.id: (s.supplier_name or s.file_name)
        for s in db.query(QuoteSource).filter(QuoteSource.batch_id == batch_id).all()
    }

    weights = normalize_weights(weight_config)

    groups: dict[str, list[QuoteItem]] = {}
    for item in items:
        groups.setdefault(_product_key(item.product_name, item.spec), []).append(item)

    result: list[dict] = []
    best_count: dict[int, int] = {}
    for group in groups.values():
        dim_scores: dict[str, dict[int, float]] = {}
        for dim in DEFAULT_WEIGHTS:
            dim_scores[dim] = _normalize(
                [(item.id, _dim_value(item, dim)) for item in group],
                dim in LOWER_BETTER,
            )

        candidates: list[dict] = []
        for item in group:
            scores = {dim: round(dim_scores[dim][item.id], 4) for dim in DEFAULT_WEIGHTS}
            total = round(sum(weights[dim] * scores[dim] for dim in DEFAULT_WEIGHTS), 4)
            candidates.append(
                _candidate(item, supplier_map.get(item.source_id, ""), scores, total)
            )
        candidates.sort(key=lambda c: c["total_score"], reverse=True)

        top = candidates[0]["total_score"]
        for cand in candidates:
            # 总分并列最优时同时高亮
            if abs(cand["total_score"] - top) < 1e-9:
                cand["is_best"] = True
                best_count[cand["source_id"]] = best_count.get(cand["source_id"], 0) + 1

        result.append(
            {
                "product_key": _product_key(group[0].product_name, group[0].spec),
                "product_name": group[0].product_name,
                "spec": group[0].spec,
                "best_supplier": candidates[0]["supplier_name"],
                "best_item_id": candidates[0]["item_id"],
                "candidates": candidates,
            }
        )

    result.sort(key=lambda g: g["product_name"])
    recommended_source_id = max(best_count, key=best_count.get) if best_count else None

    if persist:
        comparison = Comparison(
            batch_id=batch_id,
            weight_config_json=json.dumps(weights, ensure_ascii=False),
            result_json=json.dumps(result, ensure_ascii=False),
            recommended_source_id=recommended_source_id,
        )
        db.add(comparison)
        batch.status = "compared"
        db.commit()

    return {
        "batch_id": batch_id,
        "weights": weights,
        "recommended_source_id": recommended_source_id,
        "recommended_supplier": supplier_map.get(recommended_source_id, "") if recommended_source_id else "",
        "result": result,
    }