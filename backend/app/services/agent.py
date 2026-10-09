"""Agent 编排：Function Calling 工具定义与调度。

P4 阶段完整实现多轮循环；骨架阶段提供工具注册与单轮占位。
"""

from sqlalchemy.orm import Session

from app.schemas.chat import ToolResult

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
    # P3 实现真实比价引擎，当前返回占位
    return {"batch_id": args.get("batch_id"), "result": [], "message": "比价引擎待实现（P3）"}


def _exec_create_marks(db: Session, user, args: dict) -> dict:
    from app.models.mark import MarkJob

    job = MarkJob(
        template_id=args["template_id"],
        order_no=args.get("order_no", ""),
        total_boxes=args.get("total_boxes", 1),
        start_no=args.get("start_no", 1),
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "total_boxes": job.total_boxes}


TOOL_EXECUTORS = {
    "search_elements": _exec_search_elements,
    "compare_quotes": _exec_compare_quotes,
    "create_marks": _exec_create_marks,
}


def run_agent_turn(db: Session, user, session_id: int | None, content: str) -> tuple[str, list[ToolResult]]:
    """执行一轮 Agent 对话：调用 LLM → 若有 tool_calls 则执行 → 汇总回复。

    未配置 API Key 或调用失败时，降级为规则回复，保证骨架可用。
    """
    tool_results: list[ToolResult] = []
    try:
        from app.services.llm.base import get_llm_client

        client = get_llm_client()
        messages = [
            {
                "role": "system",
                "content": "你是跨境电商业务助手，可调用工具查询申报要素、比价报价、生成箱唛。",
            },
            {"role": "user", "content": content},
        ]
        response = client.chat(messages, tools=AGENT_TOOLS)
        for tc in response.get("tool_calls", []):
            fn = tc["function"]["name"]
            if fn in TOOL_EXECUTORS:
                result = TOOL_EXECUTORS[fn](db, user, tc["function"].get("arguments", {}))
                tool_results.append(ToolResult(name=fn, result=result))
        reply = response["content"] or "已为您执行工具调用，请查看结果。"
    except Exception as e:  # 降级路径：LLM 不可用时给出明确提示
        reply = f"LLM 暂不可用（{e}）。当前为骨架模式，工具能力将在后续阶段接入。"
    return reply, tool_results
