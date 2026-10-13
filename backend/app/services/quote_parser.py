"""报价单解析编排：格式路由 → 规则抽取 / LLM 增强 → 写回 QuoteItem。

Excel 走表头规则映射；Word/PDF 优先 LLM JSON 抽取，未配置 API Key 或调用失败时
自动降级为规则抽取，保证端到端可跑通。所有解析结果落库为待人工确认的明细。
"""

from sqlalchemy.orm import Session

from app.models.quote import QuoteBatch, QuoteItem, QuoteSource
from app.parsers import router as parsers


def _build_items(source: QuoteSource, rows: list[dict], base_conf: float) -> list[QuoteItem]:
    items: list[QuoteItem] = []
    for rec in rows:
        items.append(
            QuoteItem(
                source_id=source.id,
                product_name=rec.get("product_name", ""),
                spec=rec.get("spec", ""),
                unit_price=rec.get("unit_price"),
                currency=rec.get("currency") or "CNY",
                moq=rec.get("moq"),
                lead_time_days=rec.get("lead_time_days"),
                valid_until=rec.get("valid_until", ""),
                remarks=rec.get("remarks", ""),
                confidence=parsers.row_confidence(base_conf, rec),
                confirmed=False,
            )
        )
    return items


def parse_source(source: QuoteSource, db: Session) -> list[QuoteItem]:
    """解析单个报价来源，写回明细并更新来源/批次状态。"""
    file_type = source.file_type
    path = source.raw_file_url
    rows: list[dict] = []
    base_conf = 0.5

    if file_type in ("xlsx", "xls"):
        rows, base_conf = parsers.extract_excel(path)
    elif file_type in ("docx", "pdf"):
        # 先尝试 LLM 结构化抽取，失败则规则降级
        llm_rows = parsers.llm_extract(parsers.read_text(path, file_type))
        if llm_rows:
            rows, base_conf = llm_rows, 0.8
        elif file_type == "docx":
            rows, base_conf = parsers.extract_word(path)
        else:
            rows, base_conf = parsers.extract_pdf(path)
    elif file_type in ("png", "jpg", "jpeg"):
        # 图片报价单：多模态 LLM 优先，本地 OCR 兜底
        rows, base_conf = parsers.extract_image(path, file_type)
    else:
        rows, base_conf = [], 0.0

    # 重新解析前清空该来源的旧明细，避免重复叠加
    db.query(QuoteItem).filter(QuoteItem.source_id == source.id).delete()

    items = _build_items(source, rows, base_conf)
    db.add_all(items)
    source.parse_status = "success" if items else "failed"
    db.flush()

    _sync_batch_status(source.batch_id, db)
    db.commit()
    for item in items:
        db.refresh(item)
    return items


def parse_batch(batch_id: int, db: Session) -> list[QuoteItem]:
    """解析批次下所有来源，返回全部明细。"""
    sources = db.query(QuoteSource).filter(QuoteSource.batch_id == batch_id).all()
    all_items: list[QuoteItem] = []
    for source in sources:
        all_items.extend(parse_source(source, db))
    return all_items


def _sync_batch_status(batch_id: int, db: Session) -> None:
    batch = db.get(QuoteBatch, batch_id)
    if batch is None:
        return
    statuses = {
        s.parse_status
        for s in db.query(QuoteSource).filter(QuoteSource.batch_id == batch_id).all()
    }
    if statuses and statuses <= {"success", "failed"}:
        batch.status = "parsed"
    else:
        batch.status = "parsing"