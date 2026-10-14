"""I 组用例：供应商主数据与历史报价库。

历史报价数据走「上传 → 解析」真实链路产生，确保聚合口径与业务表一致。
"""
import io

import pytest
from openpyxl import Workbook

HEADER = ["产品名称", "规格", "单价", "币种", "最小起订量", "交货期"]

ROWS_A_USD = [
    HEADER,
    ["蓝牙耳机", "TWS", "3.5", "USD", "1000", "20"],
    ["充电线", "USB-C 1m", "1.2", "USD", "2000", "25"],
]
ROWS_A_CNY = [
    HEADER,
    ["蓝牙耳机", "TWS", "25", "CNY", "500", "18"],
]
ROWS_B_USD = [
    HEADER,
    ["蓝牙耳机", "TWS", "3.2", "USD", "500", "35"],
]


def _xlsx_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _create_supplier(client, headers, name: str, **extra) -> dict:
    payload = {"name": name, **extra}
    resp = client.post("/api/suppliers", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _seed_quotes(client, headers, batch_name: str, files: list[tuple[str, list[list]]]) -> int:
    """建批次 → 上传多个供应商报价 → 解析，返回 batch_id。"""
    batch_id = client.post(
        "/api/quotes/batches", params={"name": batch_name}, headers=headers
    ).json()["id"]
    for supplier, rows in files:
        resp = client.post(
            f"/api/quotes/batches/{batch_id}/sources",
            params={"supplier_name": supplier},
            files={"file": (f"{supplier}.xlsx", _xlsx_bytes(rows), "application/octet-stream")},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
    parsed = client.post(f"/api/quotes/batches/{batch_id}/parse", headers=headers)
    assert parsed.status_code == 200, parsed.text
    return batch_id


@pytest.fixture()
def quote_batch(client, users) -> int:
    headers = users["merchandiser"]["headers"]
    return _seed_quotes(
        client,
        headers,
        "供应商库测试批次",
        [("供应商A", ROWS_A_USD), ("供应商B", ROWS_B_USD)],
    )


# ---------------- 档案 CRUD ----------------

def test_i1_supplier_crud(client, users):
    headers = users["customs"]["headers"]
    created = _create_supplier(
        client,
        headers,
        "深圳万通电子",
        region="深圳",
        main_category="消费电子",
        contact_name="王工",
        contact_phone="13800000000",
        rating=4.5,
    )
    assert created["status"] == "active"
    assert created["rating"] == 4.5

    supplier_id = created["id"]
    got = client.get(f"/api/suppliers/{supplier_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["name"] == "深圳万通电子"

    listed = client.get("/api/suppliers", headers=headers).json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == supplier_id

    updated = client.put(
        f"/api/suppliers/{supplier_id}",
        json={"status": "paused", "remarks": "账期偏长，暂缓合作"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "paused"
    assert updated.json()["remarks"] == "账期偏长，暂缓合作"
    # 未提交的字段保持不变
    assert updated.json()["region"] == "深圳"

    assert client.delete(f"/api/suppliers/{supplier_id}", headers=users["admin"]["headers"]).status_code == 200
    assert client.get(f"/api/suppliers/{supplier_id}", headers=headers).status_code == 404


def test_i2_duplicate_name_rejected(client, users):
    headers = users["customs"]["headers"]
    _create_supplier(client, headers, "重复供应商")
    dup = client.post("/api/suppliers", json={"name": "重复供应商"}, headers=headers)
    assert dup.status_code == 400
    assert "已存在" in dup.json()["detail"]


def test_i3_update_name_conflict(client, users):
    headers = users["customs"]["headers"]
    first = _create_supplier(client, headers, "供应商甲")
    _create_supplier(client, headers, "供应商乙")
    resp = client.put(f"/api/suppliers/{first['id']}", json={"name": "供应商乙"}, headers=headers)
    assert resp.status_code == 400
    # 改成自己原来的名字应当放行
    same = client.put(f"/api/suppliers/{first['id']}", json={"name": "供应商甲"}, headers=headers)
    assert same.status_code == 200, same.text


def test_i4_invalid_status_rejected(client, users):
    headers = users["customs"]["headers"]
    bad = client.post("/api/suppliers", json={"name": "非法状态供应商", "status": "unknown"}, headers=headers)
    assert bad.status_code == 400
    supplier = _create_supplier(client, headers, "合法供应商")
    bad_update = client.put(
        f"/api/suppliers/{supplier['id']}", json={"status": "unknown"}, headers=headers
    )
    assert bad_update.status_code == 400


def test_i5_rbac_and_auth(client, users):
    # 未登录一律 401
    for path in ("/api/suppliers", "/api/suppliers/quote-stats", "/api/suppliers/quotes", "/api/suppliers/currencies"):
        assert client.get(path).status_code == 401, path

    # 业务员无权新建
    denied = client.post(
        "/api/suppliers", json={"name": "越权供应商"}, headers=users["merchandiser"]["headers"]
    )
    assert denied.status_code == 403

    # 关务可建不可删；管理员可删
    created = _create_supplier(client, users["customs"]["headers"], "权限供应商")
    assert client.delete(f"/api/suppliers/{created['id']}", headers=users["customs"]["headers"]).status_code == 403
    assert client.delete(f"/api/suppliers/{created['id']}", headers=users["admin"]["headers"]).status_code == 200


def test_i6_delete_blocked_when_quotes_exist(client, users, quote_batch):
    """有历史报价时禁止删除，提示改为暂停合作。"""
    headers = users["customs"]["headers"]
    supplier = _create_supplier(client, headers, "供应商A")

    resp = client.delete(f"/api/suppliers/{supplier['id']}", headers=users["admin"]["headers"])
    assert resp.status_code == 409
    assert "暂停合作" in resp.json()["detail"]
    # 档案仍然存在
    assert client.get(f"/api/suppliers/{supplier['id']}", headers=headers).status_code == 200

    paused = client.put(
        f"/api/suppliers/{supplier['id']}", json={"status": "paused"}, headers=headers
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"


def test_i7_list_filter_and_paging(client, users):
    headers = users["customs"]["headers"]
    _create_supplier(client, headers, "华南电子", region="广州", main_category="配件")
    _create_supplier(client, headers, "华东电子", region="杭州", main_category="家电", status="blacklisted")

    by_keyword = client.get("/api/suppliers", params={"keyword": "华南"}, headers=headers).json()
    assert by_keyword["total"] == 1
    assert by_keyword["items"][0]["name"] == "华南电子"

    by_status = client.get("/api/suppliers", params={"status": "blacklisted"}, headers=headers).json()
    assert by_status["total"] == 1
    assert by_status["items"][0]["name"] == "华东电子"

    paged = client.get("/api/suppliers", params={"page": 1, "page_size": 1}, headers=headers).json()
    assert paged["total"] == 2
    assert len(paged["items"]) == 1


# ---------------- 历史报价库 ----------------

def test_i8_quote_stats_aggregation(client, users, quote_batch):
    headers = users["customs"]["headers"]
    _create_supplier(client, headers, "供应商A", region="深圳", rating=4.0)

    body = client.get("/api/suppliers/quote-stats", headers=headers).json()
    assert body["total"] == 2
    # 报价条数降序：A 有 2 条、B 有 1 条
    assert [s["supplier_name"] for s in body["items"]] == ["供应商A", "供应商B"]

    stat_a = body["items"][0]
    assert stat_a["item_count"] == 2
    assert stat_a["priced_count"] == 2
    assert stat_a["batch_count"] == 1
    assert stat_a["product_count"] == 2
    assert stat_a["currencies"] == ["USD"]
    assert stat_a["last_quote_at"] is not None
    assert stat_a["price_stats"] == [
        {
            "currency": "USD",
            "item_count": 2,
            "avg_price": pytest.approx((3.5 + 1.2) / 2, rel=1e-6),
            "min_price": 1.2,
            "max_price": 3.5,
        }
    ]
    # 已建档则回填档案信息
    assert stat_a["supplier_id"] is not None
    assert stat_a["status"] == "active"
    assert stat_a["rating"] == 4.0
    assert stat_a["region"] == "深圳"

    stat_b = body["items"][1]
    assert stat_b["supplier_id"] is None
    assert stat_b["status"] == ""

    filtered = client.get("/api/suppliers/quote-stats", params={"keyword": "供应商B"}, headers=headers).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["supplier_name"] == "供应商B"


def test_i9_quote_stats_multi_currency(client, users):
    """同供应商多币种报价按币种分别统计，避免跨币种求平均。"""
    headers = users["merchandiser"]["headers"]
    _seed_quotes(
        client,
        headers,
        "多币种批次",
        [("多币种供应商", ROWS_A_USD + ROWS_A_CNY[1:])],
    )
    body = client.get("/api/suppliers/quote-stats", headers=headers).json()
    assert body["total"] == 1
    stat = body["items"][0]
    assert stat["currencies"] == ["CNY", "USD"]
    assert [p["currency"] for p in stat["price_stats"]] == ["CNY", "USD"]
    usd = next(p for p in stat["price_stats"] if p["currency"] == "USD")
    cny = next(p for p in stat["price_stats"] if p["currency"] == "CNY")
    assert usd["item_count"] == 2
    assert cny["item_count"] == 1
    assert cny["avg_price"] == 25.0


def test_i10_quote_search_filters(client, users, quote_batch):
    headers = users["merchandiser"]["headers"]

    all_quotes = client.get("/api/suppliers/quotes", headers=headers).json()
    assert all_quotes["total"] == 3

    by_product = client.get("/api/suppliers/quotes", params={"keyword": "蓝牙耳机"}, headers=headers).json()
    assert by_product["total"] == 2
    assert {q["product_name"] for q in by_product["items"]} == {"蓝牙耳机"}

    by_supplier = client.get(
        "/api/suppliers/quotes", params={"supplier_name": "供应商A"}, headers=headers
    ).json()
    assert by_supplier["total"] == 2
    assert {q["supplier_name"] for q in by_supplier["items"]} == {"供应商A"}

    by_currency = client.get("/api/suppliers/quotes", params={"currency": "CNY"}, headers=headers).json()
    assert by_currency["total"] == 0

    paged = client.get("/api/suppliers/quotes", params={"page": 2, "page_size": 2}, headers=headers).json()
    assert paged["total"] == 3
    assert len(paged["items"]) == 1

    row = all_quotes["items"][0]
    assert row["batch_name"] == "供应商库测试批次"
    assert row["quote_time"] is not None


def test_i11_supplier_quotes_detail(client, users, quote_batch):
    headers = users["customs"]["headers"]
    supplier = _create_supplier(client, headers, "供应商B")

    detail = client.get(f"/api/suppliers/{supplier['id']}/quotes", headers=headers).json()
    assert detail["total"] == 1
    assert detail["items"][0]["product_name"] == "蓝牙耳机"
    assert detail["items"][0]["unit_price"] == 3.2

    none = client.get(f"/api/suppliers/{supplier['id']}/quotes", params={"currency": "CNY"}, headers=headers).json()
    assert none["total"] == 0

    assert client.get("/api/suppliers/9999/quotes", headers=headers).status_code == 404


def test_i12_currencies_and_empty_states(client, users):
    headers = users["merchandiser"]["headers"]
    assert client.get("/api/suppliers/currencies", headers=headers).json() == []

    empty_stats = client.get("/api/suppliers/quote-stats", headers=headers).json()
    assert empty_stats == {"items": [], "total": 0, "page": 1, "page_size": 20}
    empty_quotes = client.get("/api/suppliers/quotes", headers=headers).json()
    assert empty_quotes == {"items": [], "total": 0, "page": 1, "page_size": 20}
    assert client.get("/api/suppliers", headers=headers).json()["total"] == 0

    _seed_quotes(client, headers, "币种批次", [("供应商A", ROWS_A_USD), ("供应商B", ROWS_A_CNY)])
    assert client.get("/api/suppliers/currencies", headers=headers).json() == ["CNY", "USD"]