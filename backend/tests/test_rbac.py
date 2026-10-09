"""C 组用例：RBAC 角色权限（merchandiser < customs < admin）。"""


def _element_payload(**overrides):
    payload = {
        "hs_code": "8517.62",
        "product_name": "蓝牙耳机",
        "customer_name": "沃尔玛",
    }
    payload.update(overrides)
    return payload


def test_c1_merch_cannot_create(client, users):
    resp = client.post("/api/elements", json=_element_payload(), headers=users["merchandiser"]["headers"])
    assert resp.status_code == 403
    assert "权限不足" in resp.json()["detail"]


def test_c2_customs_can_create(client, users):
    resp = client.post("/api/elements", json=_element_payload(), headers=users["customs"]["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created_by"] == users["customs"]["user"]["id"]


def test_c3_customs_cannot_delete(client, users):
    create = client.post("/api/elements", json=_element_payload(), headers=users["customs"]["headers"])
    element_id = create.json()["id"]
    resp = client.delete(f"/api/elements/{element_id}", headers=users["customs"]["headers"])
    assert resp.status_code == 403


def test_c4_admin_can_delete(client, users):
    create = client.post("/api/elements", json=_element_payload(), headers=users["customs"]["headers"])
    element_id = create.json()["id"]
    resp = client.delete(f"/api/elements/{element_id}", headers=users["admin"]["headers"])
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # 删除后详情 404
    assert client.get(f"/api/elements/{element_id}", headers=users["customs"]["headers"]).status_code == 404


def test_c5_read_open_to_all_roles(client, users):
    for role in ("merchandiser", "customs", "admin"):
        resp = client.get("/api/elements", headers=users[role]["headers"])
        assert resp.status_code == 200, f"{role} 读取失败: {resp.text}"
