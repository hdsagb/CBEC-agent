"""报价单解析管道：格式路由 → 解析器 → LLM 结构化抽取 → 置信度标注。

格式优先级：Excel(P0) > Word/PDF(P1) > 图片OCR(P2)；Google 在线链接下载后转 xlsx。
骨架阶段：Excel 走 openpyxl 基础抽取，其余格式返回占位。
"""

from sqlalchemy.orm import Session

from app.models.quote import QuoteItem

# 各解析器返回标准化行：{product_name, spec, unit_price, currency, moq, lead_time_days, valid_until, remarks}
EXTRACTION_PROMPT = """你是报价单结构化助手。从以下表格文本中抽取报价明细，
以 JSON 输出 {"items": [...]}，每项包含：
product_name(产品名), spec(规格), unit_price(单价数字), currency(币种),
moq(最小起订量), lead_time_days(货期天数), valid_until(有效期), remarks(备注)。
对不确定的字段填 null。"""


def parse_file(file_path: str, file_type: str, db: Session | None = None) -> list[QuoteItem]:
    """按格式路由到对应解析器，返回待人工确认的 QuoteItem 列表。"""
    text_rows: list[dict] = []
    if file_type in ("xlsx", "xls"):
        text_rows = _parse_excel(file_path)
    elif file_type == "docx":
        text_rows = _parse_word(file_path)
    elif file_type == "pdf":
        text_rows = _parse_pdf(file_path)
    elif file_type in ("png", "jpg", "jpeg"):
        text_rows = _parse_ocr(file_path)

    # TODO(P1): text_rows → LLM JSON Mode 结构化抽取 + 置信度标注
    items: list[QuoteItem] = []
    if db is not None:
        pass
    return items


def _parse_excel(file_path: str) -> list[dict]:
    from openpyxl import load_workbook

    wb = load_workbook(file_path, read_only=True, data_only=True)
    rows: list[dict] = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            if row and any(cell is not None for cell in row):
                rows.append({"cells": [str(c) if c is not None else "" for c in row]})
    return rows


def _parse_word(file_path: str) -> list[dict]:
    return []  # TODO(P1): python-docx 表格抽取


def _parse_pdf(file_path: str) -> list[dict]:
    return []  # TODO(P1): pypdf 文本抽取


def _parse_ocr(file_path: str) -> list[dict]:
    return []  # TODO(P2): OCR 引擎接入


def parse_online_doc(url: str) -> list[dict]:
    """Google Sheet/Doc 在线链接：导出为 xlsx 后走 Excel 解析。"""
    return []  # TODO(P1): httpx 拉取导出内容
