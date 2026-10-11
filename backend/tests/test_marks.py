"""F 组用例：箱唛生成 F2 —— 模板 / 任务 / 300dpi PDF·PNG 导出引擎。

覆盖：模板与任务 CRUD 校验、行式与画布式版式解析、占位变量替换、
PDF 一箱一页与页面尺寸、PNG 多箱竖向拼接与像素尺寸、非法格式与越权。
"""
import json
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.core.config import settings
from app.services import mark_render

LAYOUT = {
    "width_mm": 100,
    "height_mm": 100,
    "title": "SHIPPING MARK",
    "rows": [
        "品名",
        {"label": "箱号", "value": "C/NO. {box_no} OF {total_boxes}", "bold": True},
        {"label": "订单", "value": "{order_no}"},
    ],
    "footer": "MADE IN CHINA",
}

FIELDS = {"品名": "蓝牙耳机", "毛重": "12.5 KGS"}


def _headers(users) -> dict:
    return users["merchandiser"]["headers"]


@pytest.fixture()
def template_id(client, users) -> int:
    resp = client.post(
        "/api/marks/templates",
        json={"name": "标准出口唛", "layout_json": json.dumps(LAYOUT, ensure_ascii=False)},
        headers=_headers(users),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.fixture()
def job_id(client, users, template_id) -> int:
    resp = client.post(
        "/api/marks/jobs",
        json={
            "template_id": template_id,
            "order_no": "SO-20261010-004",
            "total_boxes": 3,
            "start_no": 1,
            "fields_json": json.dumps(FIELDS, ensure_ascii=False),
        },
        headers=_headers(users),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _export(client, users, job_id: int, fmt: str):
    return client.post(
        f"/api/marks/jobs/{job_id}/export",
        json={"job_id": job_id, "format": fmt},
        headers=_headers(users),
    )


def _file_of(url: str) -> Path:
    return Path(settings.upload_dir) / mark_render.MARKS_SUBDIR / url.rsplit("/", 1)[-1]


def test_f1_create_template(client, users):
    resp = client.post(
        "/api/marks/templates",
        json={"name": "空版式"},
        headers=_headers(users),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["layout_json"] == "{}"
    assert body["name"] == "空版式"


def test_f2_list_templates_and_jobs(client, users, template_id, job_id):
    tpls = client.get("/api/marks/templates", headers=_headers(users)).json()
    assert [t["id"] for t in tpls] == [template_id]
    jobs = client.get("/api/marks/jobs", headers=_headers(users)).json()
    assert jobs[0]["id"] == job_id
    assert jobs[0]["total_boxes"] == 3


def test_f3_job_requires_existing_template(client, users):
    resp = client.post(
        "/api/marks/jobs",
        json={"template_id": 9999, "order_no": "X"},
        headers=_headers(users),
    )
    assert resp.status_code == 404


def test_f4_export_pdf_one_page_per_box(client, users, job_id):
    resp = _export(client, users, job_id, "pdf")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["url"].startswith("/uploads/marks/")
    assert body["url"].endswith(".pdf")
    assert "3" in body["message"]

    path = _file_of(body["url"])
    assert path.exists() and path.stat().st_size > 1000
    assert path.read_bytes()[:5] == b"%PDF-"

    reader = PdfReader(str(path))
    assert len(reader.pages) == 3
    box = reader.pages[0].mediabox
    assert round(float(box.width), 1) == round(100 * mark_render.MM, 1)
    assert round(float(box.height), 1) == round(100 * mark_render.MM, 1)


def test_f5_export_png_stacks_all_boxes(client, users, job_id):
    from PIL import Image

    resp = _export(client, users, job_id, "png")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["url"].endswith(".png")
    assert "3" in body["message"]

    with Image.open(_file_of(body["url"])) as img:
        width_px = round(100 / 25.4 * 300)
        assert img.size == (width_px, width_px * 3)
        assert img.getpixel((5, 5)) == (255, 255, 255)


def test_f6_rejects_unknown_format(client, users, job_id):
    assert _export(client, users, job_id, "svg").status_code == 400


def test_f7_export_missing_job_404(client, users):
    assert _export(client, users, 9999, "pdf").status_code == 404


def test_f8_export_requires_auth(client, users, job_id):
    resp = client.post(f"/api/marks/jobs/{job_id}/export", json={"job_id": job_id, "format": "pdf"})
    assert resp.status_code == 401


def test_f9_empty_layout_falls_back_to_defaults(client, users):
    """模板版式为 '{}' / 非法 JSON 时仍能导出，不抛异常。"""
    assert mark_render.load_layout("{}")["width_mm"] == 100.0
    assert mark_render.load_layout("{oops")["rows"] == []
    assert mark_render.load_layout(None)["border"] is True


def test_f10_placeholder_substitution(client, users, job_id):
    templates = client.get("/api/marks/templates", headers=_headers(users)).json()
    layout = mark_render.load_layout(templates[0]["layout_json"])

    class _Job:
        order_no = "SO-20261010-004"
        total_boxes = 5
        start_no = 1

    width, height, ops = mark_render.render_ops(layout, _Job(), FIELDS, 2)
    assert (round(width, 1), round(height, 1)) == (round(100 * mark_render.MM, 1),) * 2
    texts = [op["text"] for op in ops if op["kind"] == "text"]
    assert "箱号: C/NO. 2 OF 5" in texts          # 箱号按 box_no 递增
    assert "订单: SO-20261010-004" in texts        # 订单号来自任务
    assert "品名: 蓝牙耳机" in texts               # 字符串行取 fields_json
    assert "SHIPPING MARK" in texts and "MADE IN CHINA" in texts
    # 未知占位符渲染为空串而非原样保留
    assert mark_render._sub("{不存在}", {}) == ""


def test_f11_job_box_count_must_be_positive(client, users, template_id):
    resp = client.post(
        "/api/marks/jobs",
        json={"template_id": template_id, "order_no": "X", "total_boxes": 0},
        headers=_headers(users),
    )
    assert resp.status_code == 422


def test_f12_font_resolved_from_system():
    """字体走「系统字体优先」：解析结果必须是存在的 TrueType 文件（.ttf/.ttc）。"""
    path, index = mark_render.resolve_font()
    assert Path(path).is_file()
    assert path.lower().endswith((".ttf", ".ttc"))
    assert index == 0
    # 命中缓存，重复调用返回同一结果
    assert mark_render.resolve_font() == (path, index)


def test_f13_cff_outline_fonts_rejected(tmp_path):
    """CFF 轮廓（sfnt tag OTTO，如 fonts-noto-cjk）必须被剔除，否则 reportlab 无法嵌入。"""
    cff = tmp_path / "fake-cff.ttf"
    cff.write_bytes(b"OTTO" + b"\x00" * 32)
    assert mark_render._has_truetype_outlines(str(cff)) is False

    glyf = tmp_path / "fake-glyf.ttf"
    glyf.write_bytes(b"\x00\x01\x00\x00" + b"\x00" * 32)
    assert mark_render._has_truetype_outlines(str(glyf)) is True

    # TTC 需跳到第一个子字体的 sfnt 标记再判断
    ttc = tmp_path / "fake.ttc"
    ttc.write_bytes(
        b"ttcf"
        + (1).to_bytes(4, "big")  # 版本号
        + (1).to_bytes(4, "big")  # 子字体数量
        + (16).to_bytes(4, "big")  # 第一个子字体偏移
        + b"\x00\x01\x00\x00"
        + b"\x00" * 8
    )
    assert mark_render._has_truetype_outlines(str(ttc)) is True

    assert mark_render._has_truetype_outlines(str(tmp_path / "missing.ttf")) is False