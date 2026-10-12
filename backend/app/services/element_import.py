"""申报要素批量写入：按「HS编码 + 商品名称 + 客户名称」去重后落库。

Excel 导入（api/routers/elements.py）与 Agent 工具（services/agent.py）共用此逻辑，
避免两处去重规则各自演化。本模块只做校验、去重与写入，不解析文件。
"""

import json

from sqlalchemy.orm import Session

from app.models.declaration_element import DeclarationElement

# 必填字段与中文名（缺一即视为无效记录）
REQUIRED_FIELDS: dict[str, str] = {
    "hs_code": "HS编码",
    "product_name": "商品名称",
    "customer_name": "客户名称",
}

# 可写入的文本字段，与 element_excel.EXPORT_COLUMNS 保持一致
_TEXT_FIELDS = (
    "hs_code",
    "product_name",
    "name_en",
    "customer_name",
    "brand",
    "model",
    "spec",
    "material",
    "usage",
)

_ERROR_LIMIT = 20


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        # LLM / Excel 可能把 HS 编码给成 8517.0，去掉多余小数位
        return str(int(value))
    return str(value).strip()


def _extra_json(record: dict) -> str:
    """把 elements（键值对数组）或 elements_json（JSON 字符串）归一化为 JSON 字符串。"""
    if "elements" in record:
        items: list[dict] = []
        for item in record.get("elements") or []:
            if not isinstance(item, dict):
                continue
            name, value = _text(item.get("name")), _text(item.get("value"))
            if name or value:
                items.append({"name": name, "value": value})
        return json.dumps(items, ensure_ascii=False)
    raw = record.get("elements_json")
    if not raw:
        return "[]"
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return "[]"
    return json.dumps(data, ensure_ascii=False) if isinstance(data, list) else "[]"


def normalize(record: dict) -> tuple[dict | None, list[str]]:
    """校验并标准化单条记录。返回 (记录, 缺失的中文字段名)；缺必填项时记录为 None。"""
    data = {field: _text(record.get(field)) for field in _TEXT_FIELDS}
    data["elements_json"] = _extra_json(record)
    missing = [cn for field, cn in REQUIRED_FIELDS.items() if not data[field]]
    return (None if missing else data), missing


def bulk_import(db: Session, records: list, user_id: int) -> dict:
    """去重写入要素，返回 {created, skipped, invalid, errors}。

    去重键为 (hs_code, product_name, customer_name)：与库中已有记录重复的跳过，
    同一批内的重复行也只保留首条，均不覆盖原记录。
    """
    valid: list[dict] = []
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"第 {index} 条：格式非法，应为对象")
            continue
        data, missing = normalize(record)
        if data is None:
            errors.append(f"第 {index} 条：缺少{'、'.join(missing)}")
            continue
        valid.append(data)

    keys = {(r["hs_code"], r["product_name"], r["customer_name"]) for r in valid}
    existing: set[tuple[str, str, str]] = set()
    if keys:
        rows = (
            db.query(
                DeclarationElement.hs_code,
                DeclarationElement.product_name,
                DeclarationElement.customer_name,
            )
            .filter(DeclarationElement.hs_code.in_({k[0] for k in keys}))
            .all()
        )
        existing = {(h or "", p or "", c or "") for h, p, c in rows}

    created = 0
    skipped = 0
    for rec in valid:
        key = (rec["hs_code"], rec["product_name"], rec["customer_name"])
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        db.add(DeclarationElement(**rec, created_by=user_id, updated_by=user_id))
        created += 1
    if created:
        db.commit()

    return {
        "created": created,
        "skipped": skipped,
        "invalid": len(errors),
        "errors": errors[:_ERROR_LIMIT],
    }