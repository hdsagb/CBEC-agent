"""I 组用例：箱唛可视化编辑器 —— 画布元素、素材上传、服务端所见即所得预览。

覆盖：素材上传校验与落盘、素材增删列、block kind 分派（text / image / qrcode / barcode）、
图片元素上的占位变量替换、缺失素材与空内容处理、模板更新、预览接口产物尺寸与鉴权、
目录穿越与外链地址拒绝。
"""
import io
import json
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from app.core.config import settings
from app.services import mark_render


class _Job:
    """轻量任务对象，渲染引擎只依赖 order_no / total_boxes / start_no。"""

    def __init__(self, order_no: str = "SO-20261012-001", total_boxes: int = 2, start_no: int = 1) -> None:
        self.order_no = order_no
        self.total_boxes = total_boxes
        self.start_no = start_no


def _png_bytes(size: tuple[int, int] = (8, 8), color: tuple[int, int, int] = (200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _headers(users) -> dict:
    return users["merchandiser"]["headers"]


def _asset_file(url: str) -> Path:
    return Path(settings.upload_dir) / url.replace("/uploads/", "", 1)


CANVAS = {
    "width_mm": 120,
    "height_mm": 100,
    "border": True,
    "title": "SHIPPING MARK",
    "blocks": [
        {"kind": "text", "text": "C/NO. {box_no}/{total_boxes}", "x_mm": 6, "y_mm": 30, "w_mm": 60,
         "size": 12, "bold": True},
        {"kind": "image", "src": "__LOGO__", "x_mm": 80, "y_mm": 6, "w_mm": 30, "h_mm": 30},
        {"kind": "qrcode", "text": "https://cbec/{order_no}/{box_no}", "x_mm": 80, "y_mm": 40, "size_mm": 25},
        {"kind": "barcode", "text": "{order_no}", "x_mm": 6, "y_mm": 80, "w_mm": 70, "h_mm": 12},
    ],
}


def _layout_with(blocks: list[dict], **extra) -> dict:
    return mark_render.load_layout(json.dumps({**CANVAS, **extra, "blocks": blocks}))


def _ops_of(blocks: list[dict], logo_url: str = "", **extra) -> list[dict]:
    blocks = json.loads(json.dumps(blocks).replace("__LOGO__", logo_url or "/uploads/assets/missing.png"))
    _, _, ops = mark_render.render_ops(_layout_with(blocks, **extra), _Job(), {"品名": "蓝牙耳机"}, 1)
    return ops


@pytest.fixture()
def logo_url(client, users) -> str:
    resp = client.post(
        "/api/marks/assets",
        files={"file": ("logo.png", _png_bytes(), "image/png")},
        data={"type": "logo"},
        headers=_headers(users),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["file_url"]


@pytest.fixture()
def canvas_template_id(client, users, logo_url) -> int:
    blocks = json.loads(json.dumps(CANVAS["blocks"]).replace("__LOGO__", logo_url))
    resp = client.post(
        "/api/marks/templates",
        json={"name": "画布模板", "layout_json": json.dumps({**CANVAS, "blocks": blocks}, ensure_ascii=False)},
        headers=_headers(users),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.fixture()
def canvas_job_id(client, users, canvas_template_id) -> int:
    resp = client.post(
        "/api/marks/jobs",
        json={"template_id": canvas_template_id, "order_no": "SO-20261012-001", "total_boxes": 2, "start_no": 1,
              "fields_json": json.dumps({"品名": "蓝牙耳机"}, ensure_ascii=False)},
        headers=_headers(users),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


# ---------- 素材上传 / 增删列 ----------

def test_i1_upload_logo_asset(client, users, logo_url):
    assert logo_url.startswith("/uploads/assets/")
    assert logo_url.endswith(".png")
    path = _asset_file(logo_url)
    assert path.is_file() and path.stat().st_size > 0


def test_i2_reject_non_image_extension(client, users):
    resp = client.post(
        "/api/marks/assets",
        files={"file": ("evil.svg", b"<svg/>", "image/svg+xml")},
        headers=_headers(users),
    )
    assert resp.status_code == 400
    assert "仅支持图片素材" in resp.json()["detail"]


def test_i3_reject_empty_and_oversized(client, users):
    empty = client.post(
        "/api/marks/assets",
        files={"file": ("a.png", b"", "image/png")},
        headers=_headers(users),
    )
    assert empty.status_code == 400
    oversized = client.post(
        "/api/marks/assets",
        files={"file": ("big.png", b"\x89" + b"0" * (5 * 1024 * 1024 + 1), "image/png")},
        headers=_headers(users),
    )
    assert oversized.status_code == 400
    assert "5MB" in oversized.json()["detail"]


def test_i4_reject_undecodable_image(client, users):
    resp = client.post(
        "/api/marks/assets",
        files={"file": ("fake.png", b"not-an-image", "image/png")},
        headers=_headers(users),
    )
    assert resp.status_code == 400
    assert "图片" in resp.json()["detail"]


def test_i5_list_and_delete_asset(client, users, logo_url):
    listed = client.get("/api/marks/assets", headers=_headers(users)).json()
    assert [a["file_url"] for a in listed] == [logo_url]
    assert listed[0]["type"] == "logo"

    path = _asset_file(logo_url)
    assert path.is_file()
    resp = client.delete(f"/api/marks/assets/{listed[0]['id']}", headers=_headers(users))
    assert resp.status_code == 200
    assert not path.exists()
    assert client.get("/api/marks/assets", headers=_headers(users)).json() == []
    assert client.delete("/api/marks/assets/9999", headers=_headers(users)).status_code == 404


def test_i6_asset_endpoints_require_auth(client):
    assert client.get("/api/marks/assets").status_code == 401
    assert client.post("/api/marks/assets", files={"file": ("a.png", b"x", "image/png")}).status_code == 401


# ---------- block kind 分派 ----------

def test_i7_image_block_becomes_image_op(logo_url):
    images = [op for op in _ops_of([{"kind": "image", "src": "__LOGO__", "x_mm": 80, "y_mm": 6, "w_mm": 30, "h_mm": 30}], logo_url) if op["kind"] == "image"]
    assert len(images) == 1
    op = images[0]
    assert round(op["x"], 1) == round(80 * mark_render.MM, 1)
    assert round(op["y"], 1) == round(6 * mark_render.MM, 1)
    assert round(op["w"], 1) == round(30 * mark_render.MM, 1)
    assert round(op["h"], 1) == round(30 * mark_render.MM, 1)
    assert op["image"].width > 0 and op["image"].mode == "RGB"


def test_i8_qrcode_block_square_and_dpi_scaled(logo_url):
    images = [op for op in _ops_of([{"kind": "qrcode", "text": "{order_no}", "x_mm": 80, "y_mm": 40, "size_mm": 25}], logo_url) if op["kind"] == "image"]
    assert len(images) == 1
    op = images[0]
    expected = round(25 * mark_render.MM * 300 / 72)
    assert op["image"].size == (expected, expected)
    assert round(op["w"], 1) == round(25 * mark_render.MM, 1)


def test_i9_barcode_block_stretched_to_box(logo_url):
    images = [op for op in _ops_of([{"kind": "barcode", "text": "{order_no}", "x_mm": 6, "y_mm": 80, "w_mm": 70, "h_mm": 12}], logo_url) if op["kind"] == "image"]
    assert len(images) == 1
    op = images[0]
    assert op["image"].size == (round(70 * mark_render.MM * 300 / 72), round(12 * mark_render.MM * 300 / 72))


def test_i10_placeholder_substitution_in_image_elements(logo_url):
    layout = _layout_with([{"kind": "qrcode", "text": "https://cbec/{order_no}/{box_no}", "x_mm": 6, "y_mm": 6, "size_mm": 20}])
    context = mark_render._context(_Job(), {"品名": "蓝牙耳机"}, 3)
    assert mark_render._sub("https://cbec/{order_no}/{box_no}", context) == "https://cbec/SO-20261012-001/3"
    _, _, ops = mark_render.render_ops(layout, _Job(), {}, 3)
    assert any(op["kind"] == "image" for op in ops)


def test_i11_empty_qrcode_and_barcode_are_skipped(logo_url):
    ops = _ops_of([
        {"kind": "qrcode", "text": "", "x_mm": 6, "y_mm": 6, "size_mm": 20},
        {"kind": "barcode", "text": "   ", "x_mm": 6, "y_mm": 40, "w_mm": 40, "h_mm": 10},
        {"kind": "image", "src": "", "x_mm": 6, "y_mm": 60, "w_mm": 20, "h_mm": 20},
    ], logo_url)
    assert [op for op in ops if op["kind"] == "image"] == []


def test_i12_text_blocks_keep_backward_compatibility(logo_url):
    """省略 kind 视作 text；未知 kind 同样回落 text，不因历史版式报错。"""
    ops = _ops_of([
        {"text": "旧版式文字", "x_mm": 6, "y_mm": 8, "size": 12},
        {"kind": "signature", "text": "未知类型", "x_mm": 6, "y_mm": 20},
    ], logo_url)
    texts = [op["text"] for op in ops if op["kind"] == "text"]
    assert "旧版式文字" in texts and "未知类型" in texts
    assert [op for op in ops if op["kind"] == "image"] == []


def test_i13_missing_or_external_asset_rejected(logo_url):
    with pytest.raises(mark_render.MarkAssetMissingError):
        _ops_of([{"kind": "image", "src": "/uploads/assets/nope.png", "x_mm": 1, "y_mm": 1}], logo_url)
    with pytest.raises(mark_render.MarkAssetMissingError):
        _ops_of([{"kind": "image", "src": "https://evil.example/logo.png", "x_mm": 1, "y_mm": 1}], logo_url)
    # 目录穿越地址一律拒绝
    assert mark_render.local_asset_path("/uploads/../cbec.db") is None
    assert mark_render.local_asset_path("http://x/y.png") is None


# ---------- 模板更新 ----------

def test_i14_update_template_from_editor(client, users, canvas_template_id):
    blocks = [{"kind": "text", "text": "改版后", "x_mm": 5, "y_mm": 5, "size": 14}]
    payload = json.dumps({**CANVAS, "blocks": blocks, "width_mm": 150}, ensure_ascii=False)
    resp = client.put(
        f"/api/marks/templates/{canvas_template_id}",
        json={"name": "改版模板", "layout_json": payload},
        headers=_headers(users),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "改版模板"
    assert mark_render.load_layout(body["layout_json"])["width_mm"] == 150.0

    # 仅提交名称时版式保持不变
    only_name = client.put(
        f"/api/marks/templates/{canvas_template_id}",
        json={"name": "再改名"},
        headers=_headers(users),
    )
    assert only_name.json()["layout_json"] == payload
    assert client.put("/api/marks/templates/9999", json={"name": "x"}, headers=_headers(users)).status_code == 404


def test_i15_update_template_rejects_blank_name(client, users, canvas_template_id):
    resp = client.put(
        f"/api/marks/templates/{canvas_template_id}",
        json={"name": "   "},
        headers=_headers(users),
    )
    assert resp.status_code == 400


# ---------- 服务端预览 ----------

def test_i16_preview_returns_300dpi_png(client, users, logo_url):
    blocks = json.loads(json.dumps(CANVAS["blocks"]).replace("__LOGO__", logo_url))
    layout = {**CANVAS, "blocks": blocks}
    resp = client.post(
        "/api/marks/preview",
        json={"layout_json": json.dumps(layout, ensure_ascii=False), "fields_json": json.dumps({"品名": "蓝牙耳机"}, ensure_ascii=False),
              "order_no": "SO-20261012-001", "total_boxes": 4, "box_no": 2},
        headers=_headers(users),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["url"].startswith("/uploads/marks/") and body["url"].endswith(".png")
    path = Path(settings.upload_dir) / mark_render.MARKS_SUBDIR / body["url"].rsplit("/", 1)[-1]
    assert path.is_file()
    with Image.open(path) as img:
        assert img.size == (round(120 * mark_render.MM * 300 / 72), round(100 * mark_render.MM * 300 / 72))
        assert body["width_px"] == img.width and body["height_px"] == img.height


def test_i17_preview_requires_auth(client):
    assert client.post("/api/marks/preview", json={}).status_code == 401


def test_i18_preview_rejects_broken_layout(client, users):
    resp = client.post(
        "/api/marks/preview",
        json={"layout_json": json.dumps({"blocks": [{"kind": "image", "src": "/uploads/assets/nope.png", "x_mm": 1, "y_mm": 1}]})},
        headers=_headers(users),
    )
    assert resp.status_code == 400
    assert "素材" in resp.json()["detail"]


# ---------- 真实导出回归 ----------

def test_i19_export_with_canvas_elements(client, users, canvas_job_id):
    headers = _headers(users)
    pdf = client.post(f"/api/marks/jobs/{canvas_job_id}/export", json={"job_id": canvas_job_id, "format": "pdf"}, headers=headers)
    assert pdf.status_code == 200, pdf.text
    pdf_path = Path(settings.upload_dir) / mark_render.MARKS_SUBDIR / pdf.json()["url"].rsplit("/", 1)[-1]
    assert pdf_path.read_bytes()[:5] == b"%PDF-"
    assert len(PdfReader(str(pdf_path)).pages) == 2

    png = client.post(f"/api/marks/jobs/{canvas_job_id}/export", json={"job_id": canvas_job_id, "format": "png"}, headers=headers)
    assert png.status_code == 200, png.text
    png_path = Path(settings.upload_dir) / mark_render.MARKS_SUBDIR / png.json()["url"].rsplit("/", 1)[-1]
    with Image.open(png_path) as img:
        width_px = round(120 * mark_render.MM * 300 / 72)
        height_px = round(100 * mark_render.MM * 300 / 72)
        assert img.size == (width_px, height_px * 2)
