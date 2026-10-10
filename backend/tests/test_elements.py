"""D 组用例：申报要素库 CRUD + 筛选分页。"""
import pytest


def _payload(**overrides):
    payload = {
        "hs_code": "8517.62",
        "product_name": "蓝牙耳机",
        "name_en": "BT Earbuds",
        "customer_name": "沃尔玛",
        "brand": "ONN",
        "model": "ONN-1001",
        "spec": "TWS",
        "material": "ABS",
        "usage": "通话与音频播放",
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def sample_elements(client, users):
    """3 条要素：2 条沃尔玛（8517 系），1 条华为（8471）。"""
    payloads = [
        _payload(),
        _payload(hs_code="8517.13", product_name="手机充电线", name_en="Charging Cable",
                 brand="GE", model="GE-2002", spec="USB-C 1m"),
        _payload(hs_code="8471.30", product_name="笔记本电脑", name_en="Laptop",
                 customer_name="华为", brand="HUAWEI", model="MateBook D14", spec="14英寸"),
    ]
    ids = []
    for p in payloads:
        resp = client.post("/api/elements", json=p, headers=users["customs"]["headers"])
        assert resp.status_code == 200, resp.text
        ids.append(resp.json()["id"])
    return ids


def test_d1_create_returns_full_fields(client, users):
    resp = client.post("/api/elements", json=_payload(), headers=users["customs"]["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"] == 1
    assert body["hs_code"] == "8517.62"
    assert body["name_en"] == "BT Earbuds"
    assert body["elements_json"] == "[]"
    assert body["created_by"] == body["updated_by"] == users["customs"]["user"]["id"]


def test_d2_list_default_pagination(client, users, sample_elements):
    resp = client.get("/api/elements", headers=users["customs"]["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["items"]) == 3


def test_d3_keyword_fuzzy_search(client, users, sample_elements):
    resp = client.get("/api/elements", params={"keyword": "蓝牙"}, headers=users["customs"]["headers"])
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["product_name"] == "蓝牙耳机"


def test_d4_filter_by_hs_code_and_customer(client, users, sample_elements):
    # hs_code 子串匹配
    resp = client.get("/api/elements", params={"hs_code": "8517"}, headers=users["customs"]["headers"])
    assert {r["hs_code"] for r in resp.json()["items"]} == {"8517.62", "8517.13"}
    # 客户过滤
    resp = client.get("/api/elements", params={"customer_name": "华为"}, headers=users["customs"]["headers"])
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["customer_name"] == "华为"


def test_d5_pagination_page2(client, users, sample_elements):
    resp = client.get("/api/elements", params={"page": 2, "page_size": 2}, headers=users["customs"]["headers"])
    body = resp.json()
    # total 反映全量，items 只返回当前页
    assert body["total"] == 3
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] in sample_elements


def test_d6_pagination_validation(client, users, sample_elements):
    assert client.get("/api/elements", params={"page": 0}, headers=users["customs"]["headers"]).status_code == 422
    assert client.get("/api/elements", params={"page_size": 101}, headers=users["customs"]["headers"]).status_code == 422


def test_d7_get_detail_404(client, users, sample_elements):
    resp = client.get(f"/api/elements/{sample_elements[0]}", headers=users["customs"]["headers"])
    assert resp.status_code == 200
    assert resp.json()["id"] == sample_elements[0]
    assert client.get("/api/elements/9999", headers=users["customs"]["headers"]).status_code == 404


def test_d8_copy_reuse(client, users, sample_elements):
    src_id = sample_elements[0]
    resp = client.post(f"/api/elements/{src_id}/copy", headers=users["customs"]["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] != src_id
    assert body["product_name"] == "蓝牙耳机"
    assert body["customer_name"] == "沃尔玛"
    assert body["brand"] == "ONN"


def test_d9_partial_update(client, users, sample_elements):
    target_id = sample_elements[0]
    resp = client.put(f"/api/elements/{target_id}", json={"spec": "TWS 降噪版"},
                      headers=users["customs"]["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["spec"] == "TWS 降噪版"
    assert body["brand"] == "ONN"  # 未更新字段保持不变
    assert body["product_name"] == "蓝牙耳机"


def test_d10_delete_then_hidden_from_list(client, users, sample_elements):
    resp = client.delete(f"/api/elements/{sample_elements[0]}", headers=users["admin"]["headers"])
    assert resp.status_code == 200
    remaining = client.get("/api/elements", headers=users["customs"]["headers"]).json()
    assert remaining["total"] == 2
    assert sample_elements[0] not in [r["id"] for r in remaining["items"]]


def test_d11_declaration_text_format(client, users, sample_elements):
    resp = client.get(f"/api/elements/{sample_elements[0]}/declaration-text",
                      headers=users["customs"]["headers"])
    assert resp.status_code == 200, resp.text
    text = resp.json()["text"]
    assert "HS编码：8517.62" in text
    assert "商品名称：蓝牙耳机" in text
    assert "客户名称：沃尔玛" in text
    # 空字段（如 usage 之外的空值）不产生空行
    assert "：\n" not in text + "\n"


def test_d12_declaration_text_includes_extra_elements(client, users):
    payload = _payload(elements_json='[{"name":"成分含量","value":"ABS 60%"}]')
    created = client.post("/api/elements", json=payload, headers=users["customs"]["headers"]).json()
    resp = client.get(f"/api/elements/{created['id']}/declaration-text",
                      headers=users["customs"]["headers"])
    text = resp.json()["text"]
    assert "其它要素：" in text
    assert "成分含量：ABS 60%" in text


def test_d13_declaration_text_404(client, users, sample_elements):
    assert client.get("/api/elements/9999/declaration-text",
                      headers=users["customs"]["headers"]).status_code == 404
