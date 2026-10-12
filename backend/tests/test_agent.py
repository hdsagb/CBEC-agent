"""G 组用例：Agent 多轮工具循环。

覆盖：无工具直接作答、工具结果回喂模型、多轮累积、arguments JSON 字符串解析、
单工具异常隔离、未知工具、LLM 异常降级、轮数上限、会话历史参与推理、鉴权。

LLM 通过 monkeypatch app.services.llm.base.get_llm_client 注入假客户端，
全程不发出真实网络请求。
"""
import json

import pytest

from app.services import agent as agent_service


class FakeLLM:
    """按脚本顺序返回预置响应，并记录每次调用的 messages 便于断言。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools=None, json_mode=False):
        self.calls.append([dict(m) for m in messages])
        if not self.script:
            raise AssertionError("FakeLLM 脚本已耗尽，多调用了一次")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _tool_call(name: str, args: dict, call_id: str = "call_1") -> dict:
    """构造一次工具调用响应（arguments 为 JSON 字符串，贴近真实接口）。"""
    return {
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
            }
        ],
        "raw": {},
    }


def _text(content: str) -> dict:
    return {"content": content, "tool_calls": [], "raw": {}}


@pytest.fixture()
def patch_llm(monkeypatch):
    def _patch(script) -> FakeLLM:
        fake = FakeLLM(script)
        monkeypatch.setattr("app.services.llm.base.get_llm_client", lambda: fake)
        return fake

    return _patch


@pytest.fixture()
def llm_down(monkeypatch):
    """模拟 LLM 客户端初始化失败（未配置 API Key / provider 异常）。"""

    def _boom():
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    monkeypatch.setattr("app.services.llm.base.get_llm_client", _boom)


@pytest.fixture()
def session_id(client, users) -> int:
    resp = client.post("/api/agent/sessions", headers=users["merchandiser"]["headers"])
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _headers(users) -> dict:
    return users["merchandiser"]["headers"]


def _chat(client, users, content: str, session_id: int | None = None) -> dict:
    resp = client.post(
        "/api/agent/chat",
        json={"session_id": session_id, "content": content},
        headers=_headers(users),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _tools(parsed: str) -> list[dict]:
    return json.loads(parsed)


def _make_elements(client, users) -> None:
    payloads = [
        {"hs_code": "8517.62", "product_name": "蓝牙耳机", "customer_name": "沃尔玛"},
        {"hs_code": "8517.13", "product_name": "手机充电线", "customer_name": "沃尔玛"},
    ]
    for p in payloads:
        resp = client.post("/api/elements", json=p, headers=users["customs"]["headers"])
        assert resp.status_code == 200, resp.text


# ---------------- 基础 ----------------

def test_g1_llm_unavailable_falls_back(client, users, llm_down):
    body = _chat(client, users, "帮我查一下蓝牙耳机")
    assert "LLM 暂不可用" in body["content"]
    assert _tools(body["tool_calls_json"]) == []


def test_g2_plain_reply_without_tools(client, users, session_id, patch_llm):
    fake = patch_llm([_text("你好，我可以帮你检索申报要素、比价和生成箱唛。")])
    body = _chat(client, users, "你能做什么", session_id)
    assert body["content"] == "你好，我可以帮你检索申报要素、比价和生成箱唛。"
    assert _tools(body["tool_calls_json"]) == []
    # 首次调用上下文应为 system + 本轮用户消息
    assert [m["role"] for m in fake.calls[0]] == ["system", "user"]
    assert fake.calls[0][-1]["content"] == "你能做什么"


# ---------------- 工具回喂与多轮 ----------------

def test_g3_tool_result_fed_back_and_answered(client, users, session_id, patch_llm):
    _make_elements(client, users)
    fake = patch_llm(
        [
            _tool_call("search_elements", {"keyword": "蓝牙"}, "c1"),
            _text("共找到 1 条：蓝牙耳机（沃尔玛）。"),
        ]
    )
    body = _chat(client, users, "查一下蓝牙耳机的申报要素", session_id)

    assert body["content"] == "共找到 1 条：蓝牙耳机（沃尔玛）。"
    results = _tools(body["tool_calls_json"])
    assert len(results) == 1
    assert results[0]["name"] == "search_elements"
    assert results[0]["result"]["count"] == 1

    # 第二次调用必须带上 assistant.tool_calls 与配对的 tool 结果（回喂证据）
    roles = [m["role"] for m in fake.calls[1]]
    assert roles[-2:] == ["assistant", "tool"]
    tool_msg = fake.calls[1][-1]
    assert tool_msg["tool_call_id"] == "c1"
    assert json.loads(tool_msg["content"])["count"] == 1


def test_g4_arguments_json_string_is_parsed(client, users, session_id, patch_llm):
    """arguments 是 JSON 字符串；若未解析，keyword 过滤失效会命中 2 条。"""
    _make_elements(client, users)
    patch_llm([_tool_call("search_elements", {"keyword": "充电"}, "c1"), _text("ok")])
    body = _chat(client, users, "充电线", session_id)
    assert _tools(body["tool_calls_json"])[0]["result"]["count"] == 1


def test_g5_multiple_rounds_accumulate(client, users, session_id, patch_llm):
    _make_elements(client, users)
    patch_llm(
        [
            _tool_call("search_elements", {}, "c1"),
            _tool_call("compare_quotes", {"batch_id": 1}, "c2"),
            _text("已为你查完申报要素并按批次比价。"),
        ]
    )
    body = _chat(client, users, "先查要素再比价", session_id)
    results = _tools(body["tool_calls_json"])
    assert [r["name"] for r in results] == ["search_elements", "compare_quotes"]
    # 批次不存在属于工具级错误，不应中断整轮
    assert "error" in results[1]["result"]


# ---------------- 异常隔离 ----------------

def test_g6_tool_exception_isolated(client, users, session_id, patch_llm):
    """create_marks 收到非法 template_id，int() 抛错被隔离为 error，整轮仍完成。"""
    patch_llm(
        [
            _tool_call("create_marks", {"template_id": "abc", "total_boxes": 3}, "c1"),
            _text("模板参数有误，请提供有效模板ID。"),
        ]
    )
    body = _chat(client, users, "建个箱唛任务", session_id)
    results = _tools(body["tool_calls_json"])
    assert len(results) == 1
    assert "error" in results[0]["result"]
    assert body["content"] == "模板参数有误，请提供有效模板ID。"


def test_g7_unknown_tool_reported(client, users, session_id, patch_llm):
    patch_llm([_tool_call("no_such_tool", {}, "c1"), _text("该能力不存在。")])
    body = _chat(client, users, "调用不存在的工具", session_id)
    assert "未知工具" in _tools(body["tool_calls_json"])[0]["result"]["error"]


def test_g8_llm_error_after_tool_keeps_results(client, users, session_id, patch_llm):
    _make_elements(client, users)
    patch_llm([_tool_call("search_elements", {}, "c1"), RuntimeError("请求超时")])
    body = _chat(client, users, "查一下要素", session_id)
    assert "生成总结时出错" in body["content"]
    assert len(_tools(body["tool_calls_json"])) == 1


def test_g9_round_limit_reached(client, users, session_id, patch_llm):
    script = [_tool_call("search_elements", {}, f"c{i}") for i in range(agent_service.MAX_TOOL_ROUNDS)]
    patch_llm(script)
    body = _chat(client, users, "一直调用工具", session_id)
    assert "上限" in body["content"]
    assert len(_tools(body["tool_calls_json"])) == agent_service.MAX_TOOL_ROUNDS


# ---------------- 会话历史 ----------------

def test_g10_history_included_in_context(client, users, session_id, patch_llm):
    first = patch_llm([_text("第一轮答复")])
    _chat(client, users, "第一句", session_id)
    second = patch_llm([_text("第二轮答复")])
    _chat(client, users, "第二句", session_id)

    roles = [m["role"] for m in second.calls[0]]
    assert roles == ["system", "user", "assistant", "user"]
    assert second.calls[0][1]["content"] == "第一句"
    assert second.calls[0][2]["content"] == "第一轮答复"
    assert second.calls[0][3]["content"] == "第二句"
    assert first.script == []


# ---------------- 接口鉴权与边界 ----------------

def test_g11_tools_endpoint_requires_auth(client, users):
    assert client.get("/api/agent/tools").status_code == 401
    resp = client.get("/api/agent/tools", headers=_headers(users))
    assert resp.status_code == 200
    assert {t["name"] for t in resp.json()} == {
        "search_elements",
        "compare_quotes",
        "create_marks",
        "export_marks",
        "import_elements",
        "list_quote_batches",
    }


def test_g12_chat_rejects_foreign_session(client, users, patch_llm):
    # 另一个用户的会话不可访问
    other = client.post("/api/agent/sessions", headers=users["customs"]["headers"]).json()["id"]
    patch_llm([_text("不应被调用")])
    resp = client.post(
        "/api/agent/chat",
        json={"session_id": other, "content": "越权"},
        headers=_headers(users),
    )
    assert resp.status_code == 404


def test_g13_history_persisted_for_reload(client, users, session_id, patch_llm):
    patch_llm([_tool_call("search_elements", {}, "c1"), _text("答")])
    _chat(client, users, "问", session_id)
    resp = client.get(f"/api/agent/sessions/{session_id}/messages", headers=_headers(users))
    assert resp.status_code == 200
    rows = resp.json()
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[0]["content"] == "问"


# ---------------- H 组：工具集扩展（导出箱唛 / 批量导入要素 / 查询比价批次）----------------

MARK_LAYOUT = {"title": "SHIPPING MARK", "rows": ["品名"], "footer": "MADE IN CHINA"}


def _chat_as(client, headers, content: str, session_id: int | None = None) -> dict:
    resp = client.post(
        "/api/agent/chat",
        json={"session_id": session_id, "content": content},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _new_session(client, headers) -> int:
    resp = client.post("/api/agent/sessions", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _only_result(body: dict) -> dict:
    results = _tools(body["tool_calls_json"])
    assert len(results) == 1, results
    return results[0]["result"]


@pytest.fixture()
def mark_job_id(client, users) -> int:
    tpl = client.post(
        "/api/marks/templates",
        json={"name": "扩展测试模板", "layout_json": json.dumps(MARK_LAYOUT, ensure_ascii=False)},
        headers=_headers(users),
    )
    assert tpl.status_code == 200, tpl.text
    job = client.post(
        "/api/marks/jobs",
        json={
            "template_id": tpl.json()["id"],
            "order_no": "SO-EXT-001",
            "total_boxes": 2,
            "start_no": 1,
            "fields_json": json.dumps({"品名": "蓝牙耳机"}, ensure_ascii=False),
        },
        headers=_headers(users),
    )
    assert job.status_code == 200, job.text
    return job.json()["id"]


def test_h1_export_marks_pdf(client, users, session_id, patch_llm, mark_job_id):
    patch_llm([_tool_call("export_marks", {"job_id": mark_job_id}, "c1"), _text("已导出 PDF。")])
    result = _only_result(_chat(client, users, "把刚才的箱唛导出 PDF", session_id))
    assert result["format"] == "pdf"
    assert result["url"].startswith("/uploads/marks/") and result["url"].endswith(".pdf")
    assert "error" not in result


def test_h2_export_marks_reports_missing_job(client, users, session_id, patch_llm):
    patch_llm([_tool_call("export_marks", {"job_id": 999999}, "c1"), _text("任务不存在。")])
    result = _only_result(_chat(client, users, "导出任务 999999", session_id))
    assert "不存在" in result["error"]


def test_h3_export_marks_rejects_bad_format(client, users, session_id, patch_llm, mark_job_id):
    patch_llm([_tool_call("export_marks", {"job_id": mark_job_id, "format": "docx"}, "c1"), _text("格式不支持。")])
    result = _only_result(_chat(client, users, "导出成 word", session_id))
    assert "不支持的导出格式" in result["error"]


def test_h4_import_elements_creates_then_skips_duplicates(client, users, patch_llm):
    headers = users["customs"]["headers"]
    sid = _new_session(client, headers)
    records = [
        {
            "hs_code": "8517.62",
            "product_name": "蓝牙耳机",
            "customer_name": "沃尔玛",
            "brand": "ACME",
            "elements": [{"name": "是否无线", "value": "是"}],
        },
        {"hs_code": "8517.13", "product_name": "充电线", "customer_name": "沃尔玛"},
        {"hs_code": "8517.13", "product_name": "充电线", "customer_name": "沃尔玛"},  # 批内重复
    ]
    patch_llm([_tool_call("import_elements", {"records": records}, "c1"), _text("已导入。")])
    result = _only_result(_chat_as(client, headers, "批量导入这三条要素", sid))
    assert result["created"] == 2
    assert result["skipped"] == 1
    assert result["invalid"] == 0

    # 再次导入同一批：全部与库中已有记录重复，一律跳过
    patch_llm([_tool_call("import_elements", {"records": records}, "c1"), _text("已存在。")])
    again = _only_result(_chat_as(client, headers, "再导入一次", sid))
    assert again["created"] == 0 and again["skipped"] == 3

    # 落库校验：确为 2 条，且 elements 已写入 elements_json
    listed = client.get("/api/elements", params={"customer_name": "沃尔玛"}, headers=headers).json()
    assert listed["total"] == 2
    detail = client.get(f"/api/elements/{listed['items'][0]['id']}", headers=headers).json()
    assert detail["elements_json"] or listed["items"][1]["elements_json"]


def test_h5_import_elements_reports_invalid_rows(client, users, patch_llm):
    headers = users["customs"]["headers"]
    sid = _new_session(client, headers)
    records = [
        {"hs_code": "8517.62", "product_name": "蓝牙耳机", "customer_name": ""},  # 缺客户
        {"hs_code": "", "product_name": "无编码", "customer_name": "沃尔玛"},  # 缺 HS
        "not-an-object",  # 非对象
    ]
    patch_llm([_tool_call("import_elements", {"records": records}, "c1"), _text("部分行无效。")])
    result = _only_result(_chat_as(client, headers, "导入这几条", sid))
    assert result["created"] == 0
    assert result["invalid"] == 3
    assert len(result["errors"]) == 3


def test_h6_import_elements_requires_customs_role(client, users, session_id, patch_llm):
    """业务员无导入权限：工具返回权限错误而不是静默写入。"""
    records = [{"hs_code": "8517.62", "product_name": "蓝牙耳机", "customer_name": "沃尔玛"}]
    patch_llm([_tool_call("import_elements", {"records": records}, "c1"), _text("你没有导入权限。")])
    result = _only_result(_chat(client, users, "帮我导入要素", session_id))
    assert "权限不足" in result["error"]
    listed = client.get("/api/elements", headers=users["customs"]["headers"]).json()
    assert listed["total"] == 0


def test_h7_list_quote_batches_returns_recent(client, users, session_id, patch_llm):
    created = client.post(
        "/api/quotes/batches", params={"name": "扩展批次"}, headers=_headers(users)
    )
    assert created.status_code == 200, created.text
    patch_llm([_tool_call("list_quote_batches", {"limit": 3}, "c1"), _text("最近一个批次。")])
    result = _only_result(_chat(client, users, "最近有哪些比价批次", session_id))
    assert result["count"] == 1
    assert result["items"][0]["batch_id"] == created.json()["id"]
    assert result["items"][0]["source_count"] == 0
