"""J 组用例：要素与比价联动 —— 按 HS 编码关联历史成交价，校验报价合理性。

历史价格池走「上传 → 解析 → 确认」真实链路产生，确保与业务表口径一致。
"""
import io

import pytest
from openpyxl import Workbook

HEADER = ["产品名称", "规格", "单价", "币种", "最小起订量", "交货期"]

# 历史成交：蓝牙耳机两条（USD），充电线一条（USD）
ROWS_HISTORY = [
    HEADER,
    ["蓝牙耳机", "TWS", "3.5", "USD", "1000", "20"],
    ["蓝牙耳机", "TWS", "3.0", "USD", "800", "25"],
    ["充电线", "USB-C 1m", "1.2", "USD", "2000", "25"],
]

# 待校验批次：同一商品三种价位的报价
ROWS_CHECK = [
    HEADER,
    ["蓝牙耳机", "TWS", "3.2", "USD", "1000", "10"],
    ["蓝牙耳机", "TWS", "5.0", "USD", "1000", "10"],
    ["蓝牙耳机", "TWS", "1.0", "USD", "1000", "10"],
]

ROWS_CHECK_CNY = [
    HEADER,
    ["蓝牙耳机", "TWS", "25", "CNY", "1000", "10"],
]


def _xlsx_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _seed_batch(client, headers, batch_name: str, files: list[tuple[str, list[list]]]) -> int:
    """建批次 → 上传多家供应商报价 → 一键解析，返回 batch_id。"""
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


def _batch_items(client, headers, batch_id: int) -> list[dict]:
    resp = client.get(f"/api/quotes/batches/{batch_id}/items", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _confirm_all(client, headers, batch_id: int) -> list[dict]:
    items = _batch_items(client, headers, batch_id)
    for it in items:
        resp = client.put(
            f"/api/quotes/items/{it['id']}/confirm",
            json={
                "product_name": it["product_name"],
                "spec": it["spec"],
                "unit_price": it["unit_price"],
                "currency": it["currency"],
                "moq": it["moq"],
                "lead_time_days": it["lead_time_days"],
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
    return items


def _create_element(client, headers, name: str, hs_code: str) -> dict:
    resp = client.post(
        "/api/elements",
        json={"hs_code": hs_code, "product_name": name, "customer_name": "测试客户"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def history(client, users) -> int:
    """已确认的历史报价批次，构成历史价格池。"""
    headers = users["merchandiser"]["headers"]
    batch_id = _seed_batch(client, headers, "历史批次", [("供应商A", ROWS_HISTORY)])
    _confirm_all(client, headers, batch_id)
    return batch_id


# ---------------- 历史价格参考 ----------------

def test_j1_product_name_match(client, users, history):
    headers = users["customs"]["headers"]
    element = _create_element(client, headers, "蓝牙耳机", "8517.62")

    body = client.get(f"/api/elements/{element['id']}/price-reference", headers=headers).json()
    assert body["match_by"] == "product"
    assert body["hs_code"] == "851762"
    assert body["sample_count"] == 2

    assert len(body["currency_stats"]) == 1
    usd = body["currency_stats"][0]
    assert usd["currency"] == "USD"
    assert usd["item_count"] == 2
    assert usd["avg_price"] == pytest.approx(3.25, rel=1e-6)
    assert usd["min_price"] == 3.0
    assert usd["max_price"] == 3.5

    # 最近样本按时间倒序，仅包含命中商品
    assert len(body["samples"]) == 2
    assert {s["product_name"] for s in body["samples"]} == {"蓝牙耳机"}
    assert body["samples"][0]["supplier_name"] == "供应商A"
    assert body["samples"][0]["batch_name"] == "历史批次"


def test_j2_hs_code_fallback(client, users, history):
    """商品名不在历史报价中，回退到同 HS 编码的同类商品。"""
    headers = users["customs"]["headers"]
    # 要素库中的「蓝牙耳机」已把该 HS 编码与历史报价商品名关联起来
    _create_element(client, headers, "蓝牙耳机", "8517.62")
    element = _create_element(client, headers, "无线耳机", "8517.62")

    body = client.get(f"/api/elements/{element['id']}/price-reference", headers=headers).json()
    assert body["match_by"] == "hs_code"
    assert body["hs_code"] == "851762"
    # 归因到同 HS 编码下的「蓝牙耳机」历史价
    assert body["sample_count"] == 2
    assert body["currency_stats"][0]["avg_price"] == pytest.approx(3.25, rel=1e-6)


def test_j3_no_reference(client, users, history):
    headers = users["customs"]["headers"]
    element = _create_element(client, headers, "平板电脑", "8471.30")

    body = client.get(f"/api/elements/{element['id']}/price-reference", headers=headers).json()
    assert body["match_by"] == "none"
    assert body["sample_count"] == 0
    assert body["currency_stats"] == []
    assert body["samples"] == []


def test_j4_only_confirmed_switch(client, users):
    """未确认明细默认不计入历史价格池，开关关闭后纳入。"""
    headers = users["merchandiser"]["headers"]
    batch_id = _seed_batch(client, headers, "未确认批次", [("供应商C", ROWS_HISTORY)])
    el_headers = users["customs"]["headers"]
    element = _create_element(client, el_headers, "蓝牙耳机", "8517.62")

    strict = client.get(f"/api/elements/{element['id']}/price-reference", headers=headers).json()
    assert strict["match_by"] == "none"
    assert strict["sample_count"] == 0

    loose = client.get(
        f"/api/elements/{element['id']}/price-reference",
        params={"only_confirmed": "false"},
        headers=headers,
    ).json()
    assert loose["match_by"] == "product"
    assert loose["sample_count"] == 2


def test_j5_price_reference_not_found(client, users):
    assert client.get("/api/elements/9999/price-reference", headers=users["customs"]["headers"]).status_code == 404


# ---------------- 报价合理性校验 ----------------

def test_j6_item_price_check_verdicts(client, users, history):
    headers = users["merchandiser"]["headers"]
    element_headers = users["customs"]["headers"]
    _create_element(client, element_headers, "蓝牙耳机", "8517.62")

    batch_id = _seed_batch(client, headers, "待校验批次", [("供应商X", ROWS_CHECK)])
    items = {round(it["unit_price"], 2): it for it in _batch_items(client, headers, batch_id)}
    assert set(items) == {1.0, 3.2, 5.0}

    # 合理区间 [2.6, 3.9]
    normal = client.post(f"/api/quotes/items/{items[3.2]['id']}/price-check", json={}, headers=headers).json()
    assert normal["verdict"] == "normal"
    assert normal["match_by"] == "product"
    assert normal["reference_avg"] == pytest.approx(3.25, rel=1e-6)
    assert normal["sample_count"] == 2
    assert "合理区间" in normal["message"]

    high = client.post(f"/api/quotes/items/{items[5.0]['id']}/price-check", json={}, headers=headers).json()
    assert high["verdict"] == "high"
    assert high["deviation_rate"] == pytest.approx(0.5385, abs=1e-4)
    assert "高于历史均价" in high["message"]

    low = client.post(f"/api/quotes/items/{items[1.0]['id']}/price-check", json={}, headers=headers).json()
    assert low["verdict"] == "low"
    assert "低于历史均价" in low["message"]


def test_j7_item_check_tolerance_and_override(client, users, history):
    headers = users["merchandiser"]["headers"]
    batch_id = _seed_batch(client, headers, "容差批次", [("供应商X", ROWS_CHECK)])
    items = {round(it["unit_price"], 2): it for it in _batch_items(client, headers, batch_id)}

    # 用请求体覆盖单价并指定极宽容差，任何价格都判为合理
    resp = client.post(
        f"/api/quotes/items/{items[3.2]['id']}/price-check",
        json={"unit_price": 3.3, "currency": "USD", "tolerance": 0.5},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["unit_price"] == 3.3
    assert body["verdict"] == "normal"

    # 无历史参考时返回 no_reference
    none_ref = client.post(
        f"/api/quotes/items/{items[3.2]['id']}/price-check",
        json={"product_name": "不存在的商品", "hs_code": "000000"},
        headers=headers,
    ).json()
    assert none_ref["verdict"] == "no_reference"
    assert none_ref["match_by"] == "none"
    assert "暂无历史参考价" in none_ref["message"]


def test_j8_currency_mismatch_is_no_reference(client, users, history):
    """历史池仅有 USD，CNY 报价无法直接比较，应提示币种样本缺失。"""
    headers = users["merchandiser"]["headers"]
    batch_id = _seed_batch(client, headers, "CNY批次", [("供应商Y", ROWS_CHECK_CNY)])
    item = _batch_items(client, headers, batch_id)[0]

    body = client.post(f"/api/quotes/items/{item['id']}/price-check", json={}, headers=headers).json()
    assert body["verdict"] == "no_reference"
    assert body["match_by"] == "product"
    assert "CNY" in body["message"]


def test_j9_batch_price_check_summary(client, users, history):
    headers = users["merchandiser"]["headers"]
    batch_id = _seed_batch(client, headers, "批量校验批次", [("供应商X", ROWS_CHECK)])

    body = client.post(f"/api/quotes/batches/{batch_id}/price-check", json={}, headers=headers).json()
    assert body["batch_id"] == batch_id
    assert body["total"] == 3
    assert (body["low"], body["normal"], body["high"], body["no_reference"]) == (1, 1, 1, 0)

    verdicts = {round(r["unit_price"], 2): r["verdict"] for r in body["items"]}
    assert verdicts == {3.2: "normal", 5.0: "high", 1.0: "low"}
    assert all(r["supplier_name"] == "供应商X" for r in body["items"])


def test_j10_batch_excludes_own_samples(client, users):
    """只有一个批次时，本批次明细不计入参考，全部为无参考。"""
    headers = users["merchandiser"]["headers"]
    batch_id = _seed_batch(client, headers, "孤立批次", [("供应商X", ROWS_CHECK)])
    _confirm_all(client, headers, batch_id)

    body = client.post(f"/api/quotes/batches/{batch_id}/price-check", json={}, headers=headers).json()
    assert body["total"] == 3
    assert body["no_reference"] == 3
    assert all(r["match_by"] == "none" for r in body["items"])


def test_j11_price_check_not_found(client, users):
    headers = users["merchandiser"]["headers"]
    assert client.post("/api/quotes/items/9999/price-check", json={}, headers=headers).status_code == 404
    assert client.post("/api/quotes/batches/9999/price-check", json={}, headers=headers).status_code == 404


# ---------------- 鉴权 ----------------

def test_j12_rbac_and_auth(client, users):
    paths = [
        ("get", "/api/elements/1/price-reference"),
        ("post", "/api/quotes/items/1/price-check"),
        ("post", "/api/quotes/batches/1/price-check"),
    ]
    for method, path in paths:
        resp = client.get(path) if method == "get" else client.post(path, json={})
        assert resp.status_code == 401, path

    # 只读角色（业务员）可正常读取参考价，不构成越权
    headers = users["merchandiser"]["headers"]
    element = _create_element(client, users["customs"]["headers"], "蓝牙耳机", "8517.62")
    ok = client.get(f"/api/elements/{element['id']}/price-reference", headers=headers)
    assert ok.status_code == 200