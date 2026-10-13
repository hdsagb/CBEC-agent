"""I 组用例：图片报价单识别（多模态 LLM 优先 + 本地 OCR 兜底）。

覆盖：base64 图片编码、OCR 文字框重建表格矩阵、多模态请求结构、
LLM 优先与 OCR 降级的分支选择、两条链路都不可用时的空结果、
以及 png 经由 HTTP 上传 → 解析的端到端路由。
"""
import json
import os

import pytest

from app.parsers import router as parsers

# 模拟 OCR 输出：(y_center, x_left, text)，三行五列的中文报价表
OCR_LINES = [
    (30.0, 40.0, "产品名称"),
    (30.0, 230.0, "规格"),
    (30.0, 420.0, "单价"),
    (30.0, 610.0, "最小起订量"),
    (30.0, 800.0, "交货期"),
    (110.0, 40.0, "蓝牙耳机"),
    (110.0, 230.0, "TWS"),
    (110.0, 420.0, "3.9"),
    (110.0, 610.0, "800"),
    (110.0, 800.0, "28"),
    (190.0, 40.0, "充电线"),
    (190.0, 230.0, "USB-C 1m"),
    (190.0, 420.0, "1.5"),
    (190.0, 610.0, "1000"),
    (190.0, 800.0, "20"),
]

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"


class _FakeVisionClient:
    """多模态客户端替身：记录请求体并返回固定 JSON。"""

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools=None, json_mode=False):
        self.calls.append(messages)
        return {"content": json.dumps(self.payload)}


def test_i1_image_data_url_encodes_base64(tmp_path):
    path = tmp_path / "quote.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    url = parsers.image_data_url(str(path), "png")
    assert url.startswith("data:image/png;base64,")
    assert url.split(",", 1)[1]


def test_i2_matrix_from_ocr_groups_rows_by_y():
    matrix = parsers._matrix_from_ocr(OCR_LINES)
    assert len(matrix) == 3
    assert matrix[0] == ["产品名称", "规格", "单价", "最小起订量", "交货期"]
    assert matrix[1] == ["蓝牙耳机", "TWS", "3.9", "800", "28"]
    assert matrix[2] == ["充电线", "USB-C 1m", "1.5", "1000", "20"]


def test_i3_llm_extract_image_sends_multimodal_payload(tmp_path, monkeypatch):
    from app.services.llm import base as llm_base

    fake = _FakeVisionClient(
        {"items": [{"product_name": "蓝牙耳机", "spec": "TWS", "unit_price": "3.9"}]}
    )
    monkeypatch.setattr(llm_base, "get_vision_client", lambda: fake)

    path = tmp_path / "quote.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    rows = parsers.llm_extract_image(str(path), "png")

    assert rows is not None and len(rows) == 1
    assert rows[0]["product_name"] == "蓝牙耳机"
    assert rows[0]["unit_price"] == 3.9

    content = fake.calls[0][1]["content"]
    assert isinstance(content, list)
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_i4_llm_extract_image_returns_none_without_vision_config(tmp_path, monkeypatch):
    from app.services.llm import base as llm_base

    monkeypatch.setattr(llm_base, "get_vision_client", lambda: None)
    path = tmp_path / "quote.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert parsers.llm_extract_image(str(path), "png") is None


def test_i5_extract_image_prefers_multimodal_llm(monkeypatch):
    ocr_called = {"flag": False}
    monkeypatch.setattr(
        parsers, "llm_extract_image", lambda _p, _t: [{"product_name": "耳机", "unit_price": 1.0}]
    )
    monkeypatch.setattr(
        parsers, "ocr_lines", lambda _p: ocr_called.__setitem__("flag", True) or []
    )

    rows, conf = parsers.extract_image("quote.png", "png")
    assert conf == 0.8
    assert rows[0]["product_name"] == "耳机"
    assert ocr_called["flag"] is False


def test_i6_extract_image_falls_back_to_ocr(monkeypatch):
    monkeypatch.setattr(parsers, "llm_extract_image", lambda _p, _t: None)
    monkeypatch.setattr(parsers, "ocr_lines", lambda _p: list(OCR_LINES))

    rows, conf = parsers.extract_image("quote.png", "png")
    assert conf == 0.6
    assert len(rows) == 2
    assert rows[0]["product_name"] == "蓝牙耳机"
    assert rows[0]["unit_price"] == 3.9
    assert rows[0]["moq"] == 800
    assert rows[1]["lead_time_days"] == 20


def test_i7_extract_image_empty_when_both_unavailable(monkeypatch):
    monkeypatch.setattr(parsers, "llm_extract_image", lambda _p, _t: None)
    monkeypatch.setattr(parsers, "ocr_lines", lambda _p: [])

    rows, conf = parsers.extract_image("quote.png", "png")
    assert rows == []
    assert conf == 0.6


def test_i8_png_upload_parses_through_http_route(client, users, monkeypatch):
    """png 上传 → 解析：真实 extract_image 分支，仅替身化 LLM/OCR 引擎。"""
    monkeypatch.setattr(parsers, "llm_extract_image", lambda _p, _t: None)
    monkeypatch.setattr(parsers, "ocr_lines", lambda _p: list(OCR_LINES))
    headers = users["merchandiser"]["headers"]

    batch = client.post(
        "/api/quotes/batches", params={"name": "图片比价"}, headers=headers
    ).json()
    uploaded = client.post(
        f"/api/quotes/batches/{batch['id']}/sources",
        params={"supplier_name": "图片供应商"},
        files={"file": ("quote.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["sources"][0]["file_type"] == "png"

    parsed = client.post(f"/api/quotes/batches/{batch['id']}/parse", headers=headers)
    assert parsed.status_code == 200, parsed.text
    items = parsed.json()
    assert len(items) == 2
    assert {i["product_name"] for i in items} == {"蓝牙耳机", "充电线"}


@pytest.mark.skipif(not os.path.exists(FONT_PATH), reason="缺少中文字体，跳过真实 OCR 校验")
def test_i9_real_ocr_engine_recognizes_chinese(tmp_path):
    """真实 RapidOCR 冒烟：确认适配层与当前版本返回结构兼容。"""
    pytest.importorskip("rapidocr")
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 240), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT_PATH, 32)
    draw.text((40, 40), "产品名称", fill="black", font=font)
    draw.text((40, 130), "蓝牙耳机", fill="black", font=font)
    path = tmp_path / "real.png"
    image.save(path)

    text = "".join(t for _, _, t in parsers.ocr_lines(str(path)))
    assert "蓝牙耳机" in text