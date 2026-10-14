"""H 组用例：数据分析报表（阶段 5）——供应商价格走势 / 报关品类分布 / 比价节省金额。

数据均由既有业务接口产生：比价报表走「上传 → 解析 → 确认 → 比价」真实链路，
确保报表口径与业务表结构一致。
"""
import io

import pytest
from openpyxl import Workbook

HEADER = ["产品名称", "规格", "单价", "币种", "最小起订量", "交货期"]

# 同币种（USD）便于节省金额直接相减
ROWS_A = [
    HEADER,
    ["蓝牙耳机", "TWS", "3.5", "USD", "1000", "20"],
    ["充电线", "USB-C 1m", "1.2", "USD", "2000", "25"],
]
ROWS_B = [
    HEADER,
    ["蓝牙耳机", "TWS", "3.2", "USD", "500", "35"],
    ["充电线", "USB-C 1m", "1.5", "USD", "1000", "20"],
]
ROWS_C = [
    HEADER,
    ["蓝牙耳机", "TWS", "3.9", "USD", "800", "28"],
]


def _xlsx_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _new_batch(client, headers, name: str = "报表测试批次") -> int:
    resp = client.post("/api/quotes/batches", params={"name": name}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _upload(client, headers, batch_id: int, rows: list[list], filename: str, supplier: str):
    resp = client.post(
        f"/api/quotes/batches/{batch_id}/sources",
        params={"supplier_name": supplier},
        files={"file": (filename, _xlsx_bytes(rows), "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def _parse_confirm_compare(client, headers, batch_id: int) -> dict:
    parsed = client.post(f"/api/quotes/batches/{batch_id}/parse", headers=headers)
    assert parsed.status_code == 200, parsed.text
    items = client.get(f"/api/quotes/batches/{batch_id}/items", headers=headers).json()
    for item in items:
        resp = client.put(
            f"/api/quotes/items/{item['id']}/confirm",
            json={
                "product_name": item["product_name"],
                "spec": item["spec"],
                "unit_price": item["unit_price"],
                "currency": item["currency"],
                "moq": item["moq"],
                "lead_time_days": item["lead_time_days"],
                "valid_until": item["valid_until"],
                "remarks": item["remarks"],
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
    compared = client.post(
        f"/api/quotes/batches/{batch_id}/compare", json={"weight_config": {}}, headers=headers
    )
    assert compared.status_code == 200, compared.text
    return compared.json()


@pytest.fixture()
def two_supplier_batch(client, users) -> int:
    headers = users["merchandiser"]["headers"]
    batch_id = _new_batch(client, headers)
    _upload(client, headers, batch_id, ROWS_A, "supplier_a.xlsx", "供应商A")
    _upload(client, headers, batch_id, ROWS_B, "supplier_b.xlsx", "供应商B")
    _parse_confirm_compare(client, headers, batch_id)
    return batch_id


# ---------------- 供应商价格走势 ----------------

def test_h1_supplier_price_trend(client, users, two_supplier_batch):
    headers = users["merchandiser"]["headers"]
    resp = client.get("/api/reports/supplier-price-trend", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body["months"]) == 1  # 同一次上传落在同一自然月
    assert body["currencies"] == ["USD"]
    assert body["suppliers"] == ["供应商A", "供应商B"]

    point_a = next(p for p in body["points"] if p["supplier_name"] == "供应商A")
    assert point_a["month"] == body["months"][0]
    assert point_a["avg_price"] == pytest.approx((3.5 + 1.2) / 2, rel=1e-6)
    assert point_a["min_price"] == 1.2
    assert point_a["max_price"] == 3.5
    assert point_a["item_count"] == 2

    point_b = next(p for p in body["points"] if p["supplier_name"] == "供应商B")
    assert point_b["item_count"] == 2


def test_h2_trend_months_param_validation(client, users):
    headers = users["merchandiser"]["headers"]
    assert client.get("/api/reports/supplier-price-trend?months=0", headers=headers).status_code == 422
    assert client.get("/api/reports/supplier-price-trend?months=99", headers=headers).status_code == 422
    ok = client.get("/api/reports/supplier-price-trend?months=12", headers=headers)
    assert ok.status_code == 200, ok.text


def test_h3_trend_empty_without_quotes(client, users):
    headers = users["merchandiser"]["headers"]
    body = client.get("/api/reports/supplier-price-trend", headers=headers).json()
    assert body == {"months": [], "suppliers": [], "currencies": [], "points": []}


# ---------------- 报关品类分布 ----------------

def test_h4_category_distribution(client, users):
    headers = users["customs"]["headers"]
    for hs, name in [("8517.62", "蓝牙耳机"), ("8517.62", "对讲机"), ("8471.30", "笔记本电脑")]:
        resp = client.post(
            "/api/elements",
            json={"hs_code": hs, "product_name": name, "customer_name": "沃尔玛"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    body = client.get("/api/reports/category-distribution", headers=headers).json()
    assert body["total_elements"] == 3
    assert len(body["slices"]) == 2

    top = body["slices"][0]
    assert top["hs_chapter"] == "85"
    assert top["label"] == "电机、电气设备"
    assert top["element_count"] == 2
    assert top["customer_count"] == 1
    assert top["share"] == pytest.approx(2 / 3, rel=1e-3)

    second = body["slices"][1]
    assert second["hs_chapter"] == "84"
    assert second["element_count"] == 1


def test_h5_category_distribution_empty(client, users):
    body = client.get(
        "/api/reports/category-distribution", headers=users["merchandiser"]["headers"]
    ).json()
    assert body == {"total_elements": 0, "slices": []}


# ---------------- 比价节省金额 ----------------

def test_h6_savings_amount(client, users, two_supplier_batch):
    headers = users["merchandiser"]["headers"]
    body = client.get("/api/reports/savings", headers=headers).json()

    assert body["batch_count"] == 1
    assert body["group_count"] == 2
    # 蓝牙耳机 3.5→3.2、充电线 1.5→1.2，各节省 0.3
    assert body["total_savings"] == pytest.approx(0.6, rel=1e-6)
    assert body["by_currency"] == [
        {"currency": "USD", "total_savings": pytest.approx(0.6, rel=1e-6), "group_count": 2}
    ]

    earbuds = next(g for g in body["groups"] if g["product_name"] == "蓝牙耳机")
    assert earbuds["best_supplier"] == "供应商B"
    assert earbuds["best_price"] == 3.2
    assert earbuds["max_price"] == 3.5
    assert earbuds["saving"] == pytest.approx(0.3, rel=1e-6)
    assert earbuds["saving_rate"] == pytest.approx(0.3 / 3.5, rel=1e-3)

    cable = next(g for g in body["groups"] if g["product_name"] == "充电线")
    assert cable["best_supplier"] == "供应商A"
    assert cable["saving"] == pytest.approx(0.3, rel=1e-6)


def test_h7_savings_skips_single_supplier(client, users):
    """仅一家有效报价时无可比空间，不产生节省记录。"""
    headers = users["merchandiser"]["headers"]
    batch_id = _new_batch(client, headers, "单供应商批次")
    _upload(client, headers, batch_id, ROWS_C, "supplier_c.xlsx", "供应商C")
    _parse_confirm_compare(client, headers, batch_id)

    body = client.get("/api/reports/savings", headers=headers).json()
    assert body["batch_count"] == 1
    assert body["group_count"] == 0
    assert body["total_savings"] == 0
    assert body["groups"] == []


def test_h8_savings_empty(client, users):
    body = client.get("/api/reports/savings", headers=users["merchandiser"]["headers"]).json()
    assert body == {
        "total_savings": 0,
        "by_currency": [],
        "batch_count": 0,
        "group_count": 0,
        "groups": [],
    }


def test_h9_reports_require_auth(client):
    for path in ("/api/reports/supplier-price-trend", "/api/reports/category-distribution", "/api/reports/savings"):
        assert client.get(path).status_code == 401, path