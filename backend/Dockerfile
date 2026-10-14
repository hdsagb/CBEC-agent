FROM python:3.12-slim

WORKDIR /app

# 1) 箱唛导出用 reportlab 渲染中文，基础镜像不含中文字体，且必须是 TrueType 轮廓
#    （fonts-noto-cjk 为 CFF 轮廓，reportlab 无法嵌入，故用文泉驿 / Droid 兜底）
# 2) libgomp1 是 onnxruntime（RapidOCR 图片报价单识别）的运行时依赖，缺失时
#    OCR 引擎会静默降级为不可用，图片解析退化成空结果
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-wqy-microhei \
        fonts-droid-fallback \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
