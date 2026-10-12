"""Agent 编排：Function Calling 工具定义与多轮调度。

一轮对话内按「模型请求工具 → 本地执行 → 结果回喂模型」循环往复，
直到模型不再请求工具或达到轮数上限，最终由模型产出自然语言答复。
"""

import json

from sqlalchemy.orm import Session

from app.schemas.chat import ToolResult

# 单轮对话内最多的工具调用轮数，避免模型反复调用陷入死循环
MAX_TOOL_ROUNDS = 5
# 参与推理的历史消息条数上限（含本轮用户消息），控制上下文长度
MAX_HISTORY_MESSAGES = 20

SYSTEM_PROMPT = (
    "你是跨境电商业务助手，可调用工具检索申报要素、批量导入申报要素、对比与查询供应商报价批次、"
    "创建并导出箱唛任务。"
    "需要真实数据时必须先调用工具获取结果，再依据工具返回内容用简洁中文作答，不要编造数据；"
    "工具结果里出现 error 字段时如实说明原因并给出可行的下一步建议。"
)

# OpenAI 兼容 function 定义
AGENT_TOOLS: list[dict] = [
    {
        "name": "search_elements",
        "description": "按关键词/客户/HS编码检索申报要素库，返回匹配的要素记录",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "产品名或英文名关键词"},
                "customer_name": {"type": "string", "description": "客户名称"},
                "hs_code": {"type": "string", "description": "HS编码（支持前缀）"},
            },
        },
    },
    {
        "name": "compare_quotes",
        "description": "对指定比价批次执行多维度加权比价，返回排序与推荐供应商",
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {"type": "integer", "description": "比价批次ID"},
                "weights": {"type": "object", "description": "维度权重，如 price/moq/lead_time"},
            },
            "required": ["batch_id"],
        },
    },
    {
        "name": "create_marks",
        "description": "根据订单信息创建箱唛生成任务（选择模板、箱数、起始箱号）",
        "parameters": {
            "type": "object",
            "properties": {
                "template_id": {"type": "integer", "description": "箱唛模板ID"},
                "order_no": {"type": "string", "description": "订单号"},
                "total_boxes": {"type": "integer", "description": "总箱数"},
                "start_no": {"type": "integer", "description": "起始箱号"},
            },
            "required": ["template_id", "order_no", "total_boxes"],
        },
    },
    {
        "name": "export_marks",
        "description": "把已有箱唛任务导出为 300dpi 文件并返回下载地址（PDF 一箱一页，PNG 多箱竖向拼接）",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "箱唛任务ID，可由 create_marks 返回或任务列表获取"},
                "format": {"type": "string", "enum": ["pdf", "png"], "description": "导出格式，默认 pdf"},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "import_elements",
        "description": (
            "批量导入申报要素记录（需关务员及以上权限）。按 HS编码+商品名称+客户名称 去重，"
            "库中已有或本批重复的记录跳过不覆盖"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "records": {
                    "type": "array",
                    "description": "待导入的要素记录数组，每项至少含 hs_code / product_name / customer_name",
                    "items": {
                        "type": "object",
                        "properties": {
                            "hs_code": {"type": "string", "description": "HS编码"},
                            "product_name": {"type": "string", "description": "商品名称"},
                            "customer_name": {"type": "string", "description": "客户名称"},
                            "name_en": {"type": "string", "description": "英文名称"},
                            "brand": {"type": "string", "description": "品牌"},
                            "model": {"type": "string", "description": "型号"},
                            "spec": {"type": "string", "description": "规格"},
                            "material": {"type": "string", "description": "材质"},
                            "usage": {"type": "string", "description": "用途"},
                            "elements": {
                                "type": "array",
                                "description": "其它申报要素，键值对数组",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "string"},
                                    },
                                },
                            },
                        },
                        "required": ["hs_code", "product_name", "customer_name"],
                    },
                }
            },
            "required": ["records"],
        },
    },
    {
        "name": "list_quote_batches",
        "description": "查询比价批次列表（含状态与供应商数量），拿到 batch_id 后可再调用 compare_quotes 看结果",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回条数，默认 5，最多 50"},
            },
        },
    },
]


def _exec_search_elements(db: Session, user, args: dict) -> dict:
    from app.models.declaration_element import DeclarationElement

    q = db.query(DeclarationElement)
    if args.get("customer_name"):
        q = q.filter(DeclarationElement.customer_name.contains(args["customer_name"]))
    if args.get("hs_code"):
        q = q.filter(DeclarationElement.hs_code.startswith(args["hs_code"]))
    if args.get("keyword"):
        q = q.filter(DeclarationElement.product_name.contains(args["keyword"]))
    rows = q.limit(10).all()
    return {
        "count": len(rows),
        "items": [
            {"id": r.id, "product_name": r.product_name, "hs_code": r.hs_code, "customer_name": r.customer_name}
            for r in rows
        ],
    }


def _exec_compare_quotes(db: Session, user, args: dict) -> dict:
    from app.services.comparison import compare_batch

    batch_id = args.get("batch_id")
    if batch_id is None:
        return {"error": "缺少 batch_id"}
    try:
        result = compare_batch(db, int(batch_id), args.get("weights") or None)
    except ValueError as e:
        return {"error": str(e)}
    return {
        "batch_id": result["batch_id"],
        "weights": result["weights"],
        "recommended_source_id": result["recommended_source_id"],
        "recommended_supplier": result["recommended_supplier"],
        "products": [
            {
                "product_name": g["product_name"],
                "spec": g["spec"],
                "best_supplier": g["best_supplier"],
                "best_item_id": g["best_item_id"],
            }
            for g in result["result"]
        ],
    }


def _exec_create_marks(db: Session, user, args: dict) -> dict:
    from app.models.mark import MarkJob, MarkTemplate

    template_id = args.get("template_id")
    if template_id is None:
        return {"error": "缺少 template_id"}
    template = db.get(MarkTemplate, int(template_id))
    if template is None:
        return {"error": f"箱唛模板不存在: {template_id}"}

    total_boxes = int(args.get("total_boxes", 1))
    if total_boxes < 1:
        return {"error": "总箱数必须大于 0"}
    job = MarkJob(
        template_id=template.id,
        order_no=str(args.get("order_no", "")),
        total_boxes=total_boxes,
        start_no=int(args.get("start_no", 1)),
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "template_id": job.template_id, "total_boxes": job.total_boxes}


def _exec_export_marks(db: Session, user, args: dict) -> dict:
    """导出箱唛任务为 PDF / PNG，复用与页面导出相同的渲染引擎。"""
    from app.models.mark import MarkJob, MarkTemplate
    from app.services import mark_render

    job_id = args.get("job_id")
    if job_id is None:
        return {"error": "缺少 job_id"}
    try:
        job = db.get(MarkJob, int(job_id))
    except (TypeError, ValueError):
        return {"error": f"非法的 job_id: {job_id}"}
    if job is None:
        return {"error": f"箱唛任务不存在: {job_id}"}
    template = db.get(MarkTemplate, job.template_id)
    if template is None:
        return {"error": f"任务引用的模板不存在: {job.template_id}"}

    fmt = str(args.get("format") or "pdf").lower()
    if fmt not in ("pdf", "png"):
        return {"error": f"不支持的导出格式: {fmt}（仅支持 pdf / png）"}
    try:
        result = mark_render.export_box_mark(job, template, fmt)
    except (mark_render.MarkAssetMissingError, mark_render.MarkBarcodeError) as exc:
        return {"error": str(exc)}
    except mark_render.MarkFontMissingError as exc:
        return {"error": f"缺少可用的中文 TrueType 字体，无法导出: {exc}"}
    return {
        "job_id": job.id,
        "format": fmt,
        "url": result["url"],
        "message": result["message"],
    }


def _exec_import_elements(db: Session, user, args: dict) -> dict:
    """批量导入申报要素；权限与页面导入一致，需关务员及以上角色。"""
    from app.api.deps import ROLE_HIERARCHY
    from app.services.element_import import bulk_import

    if ROLE_HIERARCHY.get(user.role, -1) < ROLE_HIERARCHY["customs"]:
        return {"error": "权限不足：批量导入申报要素需要关务员及以上角色"}

    records = args.get("records")
    if not isinstance(records, list) or not records:
        return {"error": "records 不能为空，请提供待导入的要素记录数组"}
    return {"total": len(records), **bulk_import(db, records, user.id)}


def _exec_list_quote_batches(db: Session, user, args: dict) -> dict:
    from app.models.quote import QuoteBatch

    try:
        limit = int(args.get("limit") or 5)
    except (TypeError, ValueError):
        limit = 5
    limit = max(1, min(limit, 50))
    rows = db.query(QuoteBatch).order_by(QuoteBatch.created_at.desc()).limit(limit).all()
    return {
        "count": len(rows),
        "items": [
            {
                "batch_id": row.id,
                "name": row.name,
                "status": row.status,
                "source_count": len(row.sources),
            }
            for row in rows
        ],
    }


TOOL_EXECUTORS = {
    "search_elements": _exec_search_elements,
    "compare_quotes": _exec_compare_quotes,
    "create_marks": _exec_create_marks,
    "export_marks": _exec_export_marks,
    "import_elements": _exec_import_elements,
    "list_quote_batches": _exec_list_quote_batches,
}


def _parse_args(raw) -> dict:
    """OpenAI 兼容接口的 arguments 是 JSON 字符串；容错解析为 dict。"""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _execute_tool(db: Session, user, name: str, args: dict) -> dict:
    """执行单个工具并隔离异常，失败返回 {"error": ...} 供模型向用户解释。"""
    executor = TOOL_EXECUTORS.get(name)
    if executor is None:
        return {"error": f"未知工具: {name}"}
    try:
        return executor(db, user, args)
    except Exception as exc:  # noqa: BLE001 —— 工具失败不应中断整轮对话
        return {"error": f"工具执行失败: {exc}"}


def _history_messages(db: Session, session_id: int) -> list[dict]:
    """取该会话最近若干条消息（含本轮用户消息）映射为 LLM 上下文。"""
    from app.models.chat import ChatMessage

    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.desc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )
    return [
        {"role": row.role, "content": row.content}
        for row in reversed(rows)
        if row.role in ("user", "assistant") and row.content
    ]


def _fallback_reply(exc: Exception) -> str:
    return (
        f"LLM 暂不可用（{exc}）。请检查 DEEPSEEK_API_KEY 配置与网络，"
        "或改用「申报要素库 / 智能比价 / 箱唛」页面直接操作。"
    )


def run_agent_turn(db: Session, user, session_id: int) -> tuple[str, list[ToolResult]]:
    """执行一轮 Agent 对话：多轮 Function Calling 循环，直至模型给出最终答复。

    调用方需先把本轮用户消息落库，本函数据此拼装系统提示 + 会话历史。
    LLM 不可用时降级为提示文案；工具执行异常被隔离为 error 结果回喂模型。
    """
    tool_results: list[ToolResult] = []
    try:
        from app.services.llm.base import get_llm_client

        client = get_llm_client()
    except Exception as exc:  # LLM 客户端初始化失败（如未配置 API Key）
        return _fallback_reply(exc), tool_results

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(_history_messages(db, session_id))

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = client.chat(messages, tools=AGENT_TOOLS)
            tool_calls = response.get("tool_calls") or []
            if not tool_calls:
                return response.get("content") or "已完成处理，请查看上方工具结果。", tool_results

            # 先回填 assistant 的 tool_calls，再逐条追加工具结果，模型据此继续推理
            messages.append(
                {
                    "role": "assistant",
                    "content": response.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )
            for index, call in enumerate(tool_calls):
                fn = call.get("function") or {}
                name = fn.get("name", "")
                result = _execute_tool(db, user, name, _parse_args(fn.get("arguments")))
                tool_results.append(ToolResult(name=name, result=result))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or f"call_{index}",
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
        return "工具调用轮数已达上限，请缩小问题范围或分步提问。", tool_results
    except Exception as exc:  # LLM 侧异常：已执行的工具结果仍向用户汇报
        if tool_results:
            return f"工具已执行完成，但生成总结时出错（{exc}）。请查看上方工具结果。", tool_results
        return _fallback_reply(exc), tool_results