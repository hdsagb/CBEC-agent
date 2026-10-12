"""箱唛渲染引擎：把「模板版式 + 任务字段」渲染成 300dpi 的 PDF / PNG。

版式来自 MarkTemplate.layout_json，两种写法都支持（字段均可省略）：

1. 行式（最简）::

    {"title": "SHIPPING MARK", "rows": ["品名", "箱号", "毛重"], "footer": "MADE IN CHINA"}

2. 画布式（追加尺寸与绝对定位区块）::

    {"width_mm": 100, "height_mm": 100, "dpi": 300, "border": true,
     "title": "SHIPPING MARK", "rows": [...], "footer": "MADE IN CHINA",
     "blocks": [{"text": "C/NO. {box_no} OF {total_boxes}", "x_mm": 6, "y_mm": 8, "size": 12, "bold": true}]}

rows 元素可以是字符串（视作 fields_json 的键）或
``{"label": "箱号", "value": "C/NO. {box_no} OF {total_boxes}"}``。

blocks 元素是绝对定位的画布元素，用 ``kind`` 区分类型（省略即 text）：

- ``text``：``{"kind":"text","text":"...","x_mm":6,"y_mm":8,"w_mm":40,"size":12,"bold":true,"align":"left"}``
- ``image``：``{"kind":"image","src":"/uploads/assets/xxx.png","x_mm":6,"y_mm":60,"w_mm":30,"h_mm":30}``
- ``qrcode``：``{"kind":"qrcode","text":"https://x/{order_no}","x_mm":60,"y_mm":6,"size_mm":25}``
- ``barcode``：``{"kind":"barcode","text":"{order_no}","x_mm":6,"y_mm":86,"w_mm":70,"h_mm":12}``

图片类元素的内容支持占位变量；text 为空（或未选素材）时该元素跳过不绘制。
二维码用 qrcode 库、条形码用 python-barcode（Code128）在渲染时实时生成，
因此 PDF 与 PNG 两种产物上的码完全一致。

占位变量：``{order_no}`` ``{box_no}`` ``{total_boxes}`` ``{box_range}``，
以及 fields_json 中的任意键（如 ``{品名}``）。未知占位符渲染为空串。

坐标系：内部一律用「原点在左上、y 轴向下」的 pt（1/72 英寸）描述绘制指令，
PDF 落地时翻转 y，PNG 落地时按 dpi 缩放，保证两种产物视觉一致。
"""
import glob
import json
import os
import re
import uuid
from pathlib import Path

from app.core.config import settings

MM = 72.0 / 25.4  # 1 毫米对应的 pt
FONT_NAME = "NotoSansSC"
BUNDLED_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NotoSansSC-Regular.ttf"

# 中文字体搜索顺序：MARK_FONT_FILE 环境变量 > 仓库内置 > 常见系统字体路径
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",  # Windows 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",  # Windows 黑体
    r"C:\Windows\Fonts\simsun.ttc",  # Windows 宋体
    r"C:\Windows\Fonts\Deng.ttf",  # Windows 等线
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Debian/Ubuntu 文泉驿微米黑
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Debian/Ubuntu 文泉驿正黑
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",  # Debian fonts-droid-fallback
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]
FONT_GLOBS = [
    "/usr/share/fonts/**/wqy-*.ttc",
    "/usr/share/fonts/**/DroidSansFallback*.ttf",
]

_font_cache: tuple[str, int] | None = None


class MarkFontMissingError(RuntimeError):
    """系统与仓库均未找到可用的中文 TrueType 字体。"""


class MarkAssetMissingError(RuntimeError):
    """版式引用的图片素材不存在或地址非法。"""


class MarkBarcodeError(RuntimeError):
    """二维码 / 条形码内容无法编码。"""


def _has_truetype_outlines(path: str) -> bool:
    """判断字体是否为 TrueType(glyf) 轮廓。

    reportlab 只能嵌入 TrueType；Noto Sans CJK 等 .ttc/.otf 是 CFF 轮廓（sfnt tag 为
    ``OTTO``），选中它们会让 PDF 导出失败，故在此提前剔除。
    """
    try:
        with open(path, "rb") as handle:
            tag = handle.read(4)
            if tag == b"ttcf":  # TTC：跳到第一个子字体的 sfnt 版本标记
                handle.read(4)  # 版本号
                handle.read(4)  # 子字体数量
                handle.seek(int.from_bytes(handle.read(4), "big"))
                tag = handle.read(4)
    except OSError:
        return False
    return tag in (b"\x00\x01\x00\x00", b"true")


def resolve_font() -> tuple[str, int]:
    """定位可用的中文 TrueType 字体，返回 (字体文件, ttc 子字体索引)。

    reportlab 只能嵌入 TrueType 轮廓，故仅接受 TrueType 的 .ttf/.ttc。
    """
    global _font_cache
    if _font_cache is not None:
        return _font_cache

    candidates = [os.environ.get("MARK_FONT_FILE", ""), str(BUNDLED_FONT), *FONT_CANDIDATES]
    for pattern in FONT_GLOBS:
        candidates.extend(sorted(glob.glob(pattern, recursive=True)))

    for candidate in candidates:
        if (
            candidate
            and os.path.isfile(candidate)
            and candidate.lower().endswith((".ttf", ".ttc"))
            and _has_truetype_outlines(candidate)
        ):
            _font_cache = (candidate, 0)
            return _font_cache

    raise MarkFontMissingError(
        "未找到可用的中文 TrueType 字体：请安装中文字体（如 fonts-wqy-microhei），"
        "或用 MARK_FONT_FILE 指定 TrueType 字体文件路径（.ttf/.ttc，不支持 CFF 的 .otf）"
    )


MARKS_SUBDIR = "marks"
ASSETS_SUBDIR = "assets"
MAX_PDF_PAGES = 500
MAX_PNG_BOXES = 20

# 画布元素类型：text 为默认，其余为图片类元素
BLOCK_KINDS = ("text", "image", "qrcode", "barcode")

_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")

_DEFAULTS: dict = {
    "width_mm": 100.0,
    "height_mm": 100.0,
    "dpi": 300,
    "margin_mm": 4.0,
    "border": True,
    "title": "",
    "title_size": 13.0,
    "row_size": 10.0,
    "footer": "",
    "footer_size": 9.0,
    "separator": ": ",
    "rows": [],
    "blocks": [],
}


def _num(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def load_layout(layout_json: str | None) -> dict:
    """宽松解析模板版式：非法 JSON 或非对象一律回落到默认版式。"""
    layout = dict(_DEFAULTS)
    try:
        raw = json.loads(layout_json or "{}")
    except (TypeError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        return layout
    for key in ("title", "footer", "separator"):
        if isinstance(raw.get(key), str):
            layout[key] = raw[key]
    for key in ("width_mm", "height_mm", "margin_mm", "title_size", "row_size", "footer_size"):
        if raw.get(key) is not None:
            layout[key] = _num(raw[key], layout[key])
    if raw.get("dpi") is not None:
        layout["dpi"] = max(72, int(_num(raw["dpi"], 300)))
    if isinstance(raw.get("border"), bool):
        layout["border"] = raw["border"]
    if isinstance(raw.get("rows"), list):
        layout["rows"] = raw["rows"]
    if isinstance(raw.get("blocks"), list):
        layout["blocks"] = [b for b in raw["blocks"] if isinstance(b, dict)]
    # 画布尺寸给出下限，避免 0 或负数导致除零 / 空画布
    layout["width_mm"] = max(10.0, layout["width_mm"])
    layout["height_mm"] = max(10.0, layout["height_mm"])
    return layout


def load_fields(fields_json: str | None) -> dict:
    try:
        raw = json.loads(fields_json or "{}")
    except (TypeError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _sub(text: object, ctx: dict) -> str:
    """替换 {占位符}；未知占位符输出空串。"""

    def repl(match: re.Match) -> str:
        value = ctx.get(match.group(1).strip())
        return "" if value is None else str(value)

    return _PLACEHOLDER.sub(repl, str(text))


def _join(label: str, value: object, separator: str) -> str:
    left, right = str(label).strip(), str(value).strip()
    if left and right:
        return f"{left}{separator}{right}"
    return left or right


def _context(job, fields: dict, box_no: int) -> dict:
    ctx = dict(fields)
    ctx.setdefault("order_no", job.order_no)
    ctx["box_no"] = str(box_no)
    ctx["total_boxes"] = str(job.total_boxes)
    ctx["box_range"] = f"{job.start_no}-{job.start_no + job.total_boxes - 1}"
    return ctx


def _rows_ops(layout: dict, ctx: dict) -> list[dict]:
    rows: list[dict] = []
    for item in layout["rows"]:
        if isinstance(item, dict):
            label = str(item.get("label", ""))
            raw = item.get("value")
            value = ctx.get(label, "") if raw is None else _sub(raw, ctx)
            rows.append(
                {
                    "text": _join(label, value, layout["separator"]),
                    "size": _num(item.get("size"), layout["row_size"]),
                    "align": str(item.get("align", "left")),
                    "bold": bool(item.get("bold", False)),
                }
            )
        else:
            key = str(item)
            text = _sub(key, ctx) if "{" in key else _join(key, ctx.get(key, ""), layout["separator"])
            rows.append({"text": text, "size": layout["row_size"], "align": "left", "bold": False})
    return rows


UPLOADS_PREFIX = "/uploads/"


def assets_dir() -> str:
    """素材（Logo 等）在本地的存放目录。"""
    return os.path.join(settings.upload_dir, ASSETS_SUBDIR)


def local_asset_path(url: str) -> str | None:
    """把 ``/uploads/xxx`` 形式的素材地址映射为本地绝对路径。

    非本站地址（外链）与目录穿越路径一律返回 None，由调用方报错。
    """
    if not url.startswith(UPLOADS_PREFIX):
        return None
    relative = url[len(UPLOADS_PREFIX):].replace("\\", "/")
    normalised = os.path.normpath(relative)
    if not relative or normalised.startswith(("..", "/")) or os.path.isabs(normalised):
        return None
    return os.path.join(settings.upload_dir, normalised)


def _qr_image(text: str, target_px: int):
    """把文本编码成二维码位图（正方形，边长 target_px 像素）。"""
    import qrcode
    from PIL import Image

    qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8)
    qr.add_data(text)
    try:
        qr.make(fit=True)
    except Exception as exc:  # qrcode 对超长/非法内容抛 DataOverflowError 等
        raise MarkBarcodeError(f"二维码内容无法编码: {text}") from exc
    modules = qr.modules_count + qr.border * 2
    qr.box_size = max(1, round(target_px / modules))
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((target_px, target_px), Image.NEAREST)


def _barcode_image(text: str, target_w: int, target_h: int):
    """把文本编码成 Code128 条形码位图并拉伸填满目标像素框。"""
    from barcode import Code128
    from barcode.writer import ImageWriter
    from PIL import Image

    module_height = max(1.0, target_h * 72.0 / 300.0 / MM)  # 以 300dpi 反推毫米高度
    options = {
        "module_width": 0.3,
        "module_height": module_height,
        "quiet_zone": 0.5,
        "write_text": False,  # 不写文字，避免依赖条码字体
        "text_distance": 0,
        "font_size": 0,
    }
    try:
        img = Code128(text, writer=ImageWriter()).render(options).convert("RGB")
    except Exception as exc:
        raise MarkBarcodeError(f"条形码内容无法编码: {text}") from exc
    return img.resize((target_w, target_h), Image.LANCZOS)


def _block_image(kind: str, block: dict, text: str, w_pt: float, h_pt: float, dpi: int):
    """按元素类型产出位图；文本为空时返回 None（该元素跳过不绘制）。"""
    from PIL import Image

    scale = dpi / 72.0
    target_w = max(1, round(w_pt * scale))
    target_h = max(1, round(h_pt * scale))

    if kind in ("image", "logo"):
        src = str(block.get("src") or block.get("file_url") or "").strip()
        if not src:
            return None
        path = local_asset_path(src)
        if path is None or not os.path.isfile(path):
            raise MarkAssetMissingError(f"版式引用的图片素材不存在或地址非法: {src}")
        try:
            with Image.open(path) as handle:
                handle.load()
                return handle.convert("RGB").copy()
        except OSError as exc:
            raise MarkAssetMissingError(f"图片素材无法解码: {src}") from exc

    if not text.strip():
        return None
    if kind == "qrcode":
        return _qr_image(text, target_w)
    return _barcode_image(text, target_w, target_h)


def _block_op(block: dict, layout: dict, ctx: dict, width: float, margin: float) -> dict | None:
    """把一个画布元素解析成绘制指令（text 或 image）。"""
    x = _num(block.get("x_mm"), layout["margin_mm"]) * MM
    y = _num(block.get("y_mm"), 0.0) * MM
    kind = str(block.get("kind") or "text").strip().lower()
    if kind not in BLOCK_KINDS:
        kind = "text"

    if kind == "text":
        size = _num(block.get("size"), 10.0)
        block_w = _num(block["w_mm"], 0.0) * MM if block.get("w_mm") is not None else max(0.0, width - x - margin)
        return {
            "kind": "text", "x": x, "y": y, "w": block_w,
            "text": _sub(block.get("text", ""), ctx), "size": size,
            "align": str(block.get("align", "left")), "bold": bool(block.get("bold", False)),
        }

    text = _sub(block.get("text", block.get("value", "")), ctx)
    if kind == "qrcode":
        side = max(2.0, _num(block.get("size_mm", block.get("w_mm")), 25.0)) * MM
        w_pt = h_pt = side
    elif kind == "barcode":
        default_w_mm = max(10.0, (width - x - margin) / MM)
        w_pt = max(5.0, _num(block.get("w_mm"), default_w_mm)) * MM
        h_pt = max(3.0, _num(block.get("h_mm"), 15.0)) * MM
    else:  # image / logo
        w_pt = max(1.0, _num(block.get("w_mm"), 30.0)) * MM
        h_pt = max(1.0, _num(block.get("h_mm"), 30.0)) * MM

    image = _block_image(kind, block, text, w_pt, h_pt, layout["dpi"])
    if image is None:
        return None
    return {"kind": "image", "image": image, "x": x, "y": y, "w": w_pt, "h": h_pt}


def render_ops(layout: dict, job, fields: dict, box_no: int) -> tuple[float, float, list[dict]]:
    """生成单箱的绘制指令，返回 (画布宽 pt, 画布高 pt, 指令列表)。"""
    ctx = _context(job, fields, box_no)
    margin = layout["margin_mm"] * MM
    width = layout["width_mm"] * MM
    height = layout["height_mm"] * MM
    inner_x, inner_w = margin, width - margin * 2

    ops: list[dict] = []
    if layout["border"]:
        ops.append({"kind": "rect", "x": 0.0, "y": 0.0, "w": width, "h": height, "lw": 1.2})

    cur = margin
    title = _sub(layout["title"], ctx).strip()
    if title:
        size = layout["title_size"]
        ops.append(
            {"kind": "text", "x": inner_x, "y": cur, "w": inner_w, "text": title,
             "size": size, "align": "center", "bold": True}
        )
        cur += size * 1.6
        ops.append({"kind": "line", "x1": inner_x, "y1": cur, "x2": inner_x + inner_w, "y2": cur, "lw": 0.9})
        cur += 6.0

    rows = _rows_ops(layout, ctx)
    footer = _sub(layout["footer"], ctx).strip()
    footer_h = layout["footer_size"] * 1.8 if footer else 0.0
    avail = height - margin - cur - footer_h
    if rows and avail > 0:
        row_h = avail / len(rows)
        for row in rows:
            size = row["size"]
            ops.append({"kind": "rect", "x": inner_x, "y": cur, "w": inner_w, "h": row_h, "lw": 0.6})
            ops.append(
                {"kind": "text", "x": inner_x + 5.0, "y": cur + (row_h - size) / 2, "w": inner_w - 10.0,
                 "text": row["text"], "size": size, "align": row["align"], "bold": row["bold"]}
            )
            cur += row_h
    if footer:
        size = layout["footer_size"]
        ops.append({"kind": "line", "x1": inner_x, "y1": cur, "x2": inner_x + inner_w, "y2": cur, "lw": 0.9})
        ops.append(
            {"kind": "text", "x": inner_x, "y": cur + (footer_h - size) / 2, "w": inner_w,
             "text": footer, "size": size, "align": "center", "bold": False}
        )

    for block in layout["blocks"]:
        op = _block_op(block, layout, ctx, width, margin)
        if op is not None:
            ops.append(op)
    return width, height, ops


def _ensure_pdf_font() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        path, index = resolve_font()
        pdfmetrics.registerFont(TTFont(FONT_NAME, path, subfontIndex=index))


def _split_lines(text: str) -> list[str]:
    return text.split("\n")


def render_pdf(layout: dict, job, fields: dict, out_path: str) -> int:
    """渲染多页 PDF（每箱一页），返回实际页数。"""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfgen import canvas as rl_canvas

    _ensure_pdf_font()
    pages = min(job.total_boxes, MAX_PDF_PAGES)
    pdf = rl_canvas.Canvas(str(out_path))
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setStrokeColorRGB(0, 0, 0)
    for offset in range(pages):
        width, height, ops = render_ops(layout, job, fields, job.start_no + offset)
        pdf.setPageSize((width, height))
        for op in ops:
            if op["kind"] == "rect":
                pdf.setLineWidth(op["lw"])
                pdf.rect(op["x"], height - op["y"] - op["h"], op["w"], op["h"], stroke=1, fill=0)
            elif op["kind"] == "line":
                pdf.setLineWidth(op["lw"])
                pdf.line(op["x1"], height - op["y1"], op["x2"], height - op["y2"])
            elif op["kind"] == "image":
                # 图片类元素（Logo/二维码/条形码）：op 内直接携带已生成好的位图
                pdf.drawImage(
                    ImageReader(op["image"]),
                    op["x"], height - op["y"] - op["h"], op["w"], op["h"],
                    preserveAspectRatio=False, mask="auto",
                )
            else:
                size, text = op["size"], op["text"]
                text_obj = pdf.beginText()
                text_obj.setFont(FONT_NAME, size)
                if op["bold"]:
                    text_obj.setTextRenderMode(2)  # 填充 + 描边模拟加粗
                    pdf.setLineWidth(size * 0.03)
                for index, line in enumerate(_split_lines(text)):
                    text_w = pdfmetrics.stringWidth(line, FONT_NAME, size)
                    if op["align"] == "center":
                        x = op["x"] + (op["w"] - text_w) / 2
                    elif op["align"] == "right":
                        x = op["x"] + op["w"] - text_w
                    else:
                        x = op["x"]
                    baseline = height - op["y"] - size * 0.8 - index * size * 1.25
                    text_obj.setTextOrigin(x, baseline)
                    text_obj.textOut(line)
                pdf.drawText(text_obj)
        pdf.showPage()
    pdf.save()
    return pages


def render_png_box(layout: dict, job, fields: dict, box_no: int):
    """渲染单箱 PNG 位图，返回 (PIL.Image, 宽 pt, 高 pt)。拼接与预览共用。"""
    from PIL import Image, ImageDraw, ImageFont

    dpi = layout["dpi"]
    scale = dpi / 72.0
    font_path, font_index = resolve_font()

    def px(value: float) -> float:
        return value * scale

    def line_width(value: float) -> int:
        return max(1, round(value * scale))

    width, height, ops = render_ops(layout, job, fields, box_no)
    box = Image.new("RGB", (round(px(width)), round(px(height))), "white")
    draw = ImageDraw.Draw(box)
    for op in ops:
        if op["kind"] == "rect":
            draw.rectangle(
                [px(op["x"]), px(op["y"]), px(op["x"] + op["w"]), px(op["y"] + op["h"])],
                outline="black",
                width=line_width(op["lw"]),
            )
        elif op["kind"] == "line":
            draw.line(
                [px(op["x1"]), px(op["y1"]), px(op["x2"]), px(op["y2"])],
                fill="black",
                width=line_width(op["lw"]),
            )
        elif op["kind"] == "image":
            target = (max(1, round(px(op["w"]))), max(1, round(px(op["h"]))))
            source = op["image"]
            resample = Image.LANCZOS if source.width > target[0] else Image.NEAREST
            box.paste(source.resize(target, resample), (round(px(op["x"])), round(px(op["y"]))))
        else:
            size = op["size"]
            font = ImageFont.truetype(font_path, max(1, round(px(size))), index=font_index)
            for index, line in enumerate(_split_lines(op["text"])):
                text_w = draw.textlength(line, font=font)
                if op["align"] == "center":
                    x = px(op["x"]) + (px(op["w"]) - text_w) / 2
                elif op["align"] == "right":
                    x = px(op["x"]) + px(op["w"]) - text_w
                else:
                    x = px(op["x"])
                draw.text(
                    (x, px(op["y"]) + index * px(size) * 1.25),
                    line,
                    font=font,
                    fill="black",
                    anchor="la",
                    stroke_width=1 if op["bold"] else 0,
                    stroke_fill="black",
                )
    return box, width, height


def render_png(layout: dict, job, fields: dict, out_path: str) -> int:
    """渲染 PNG：多箱按顺序竖向拼接成一张图，返回绘制的箱数。"""
    from PIL import Image

    boxes = min(job.total_boxes, MAX_PNG_BOXES)
    sheet = None
    for offset in range(boxes):
        box, _, _ = render_png_box(layout, job, fields, job.start_no + offset)
        if sheet is None:
            sheet = Image.new("RGB", (box.width, box.height * boxes), "white")
        sheet.paste(box, (0, offset * box.height))
    assert sheet is not None
    sheet.save(out_path, dpi=(layout["dpi"], layout["dpi"]))
    return boxes


def marks_dir() -> str:
    return os.path.join(settings.upload_dir, MARKS_SUBDIR)


def save_asset_bytes(data: bytes, ext: str) -> str:
    """把上传的素材落盘，返回可被版式引用的 /uploads 地址。"""
    out_dir = assets_dir()
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(out_dir, filename), "wb") as handle:
        handle.write(data)
    return f"{UPLOADS_PREFIX}{ASSETS_SUBDIR}/{filename}"


def export_preview(layout: dict, job, fields: dict, box_no: int) -> dict:
    """把「临时版式 + 字段」渲染成单箱 PNG，供可视化编辑器所见即所得预览。"""
    out_dir = marks_dir()
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    path = os.path.join(out_dir, filename)
    image, width, height = render_png_box(layout, job, fields, box_no)
    image.save(path, dpi=(layout["dpi"], layout["dpi"]))
    return {
        "filename": filename,
        "path": path,
        "url": f"/uploads/{MARKS_SUBDIR}/{filename}",
        "width_px": image.width,
        "height_px": image.height,
        "message": f"预览已生成（{round(width / MM)}×{round(height / MM)}mm @ {layout['dpi']}dpi）",
    }


def export_box_mark(job, template, fmt: str) -> dict:
    """把任务渲染成文件，返回 {format, filename, path, url, message, boxes}。"""
    layout = load_layout(template.layout_json)
    fields = load_fields(job.fields_json)
    out_dir = marks_dir()
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{fmt}"
    path = os.path.join(out_dir, filename)

    if fmt == "pdf":
        drawn = render_pdf(layout, job, fields, path)
        message = f"已生成 {drawn} 页箱唛 PDF"
        if drawn < job.total_boxes:
            message += f"（超出单次上限 {MAX_PDF_PAGES} 箱已截断，共 {job.total_boxes} 箱）"
    elif fmt == "png":
        drawn = render_png(layout, job, fields, path)
        message = f"PNG 已竖向拼接 {drawn} 箱"
        if drawn < job.total_boxes:
            message += f"，其余请导出 PDF（共 {job.total_boxes} 箱）"
    else:
        raise ValueError(f"不支持的导出格式: {fmt}")

    return {
        "format": fmt,
        "filename": filename,
        "path": path,
        "url": f"/uploads/{MARKS_SUBDIR}/{filename}",
        "message": message,
        "boxes": drawn,
    }