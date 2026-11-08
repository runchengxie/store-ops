"""Authenticated MCP transport for shared evidence and eMAG tools."""
from __future__ import annotations

import json
import logging
import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.services import mcp_tokens

logger = logging.getLogger("ivyea.routers.mcp_server")
router = APIRouter()

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "ivyea-ops", "version": "1"}

# 每令牌每分钟的调用上限。挡的不是攻击（令牌泄漏了限速也救不了），是**失控的
# Agent 循环** —— 对面一个写坏的 while 循环能把这台自托管机器的 CPU 和上游
# API 配额一起烧光，而用户往往到收到账单才发现。
_RATE_PER_MIN = 60
_hits: Dict[str, Deque[float]] = {}
_hits_lock = Lock()


def _schema(props: Optional[dict] = None, required: Optional[list] = None) -> dict:
    return {"type": "object", "properties": props or {},
            "required": required or [], "additionalProperties": False}


# 店铺变更仍未开放；唯一写工具是保存本地巡检报告。
TOOLS: Dict[str, dict] = {
    "ivyea_knowledge_search": {
        "description": "Search the local shared knowledge library and return source-labelled references.",
        "inputSchema": _schema({"query": {"type": "string"}, "limit": {"type": "integer", "default": 8, "minimum": 1, "maximum": 50}}, ["query"]),
        "scope": "read",
    },
    "ivyea_emag_knowledge_search": {
        "description": "Search private historical eMAG training evidence with revision-bound citations and conflicts; untrusted references, not current platform policy.",
        "inputSchema": _schema({"query": {"type": "string", "maxLength": 500}, "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20}}, ["query"]),
        "scope": "read",
    },
    "ivyea_emag_clearance_review": {
        "description": "Read snapshot-bound existing-stock priorities and an optional earlier baseline comparison; no live calls, approvals or merchant writes.",
        "inputSchema": _schema({"store_id": {"type": "string"}, "baseline_snapshot_id": {"type": "string"}}, ["store_id"]),
        "scope": "read",
    },
    "ivyea_emag_job_status": {
        "description": "读取最近手动 eMAG 巡检回执，区分新采集、离线重放及失败阶段；不启动采集。",
        "inputSchema": _schema({"store_id": {"type": "string"}}, ["store_id"]),
        "scope": "read",
    },
    "ivyea_store_snapshot": {
        "description": "读取最近导入的店铺快照，包含采集时间、来源、覆盖范围与限制；不是实时店铺查询。",
        "inputSchema": _schema({"store_id": {"type": "string"}}, ["store_id"]),
        "scope": "read",
    },
    "ivyea_report_save": {
        "description": "保存本地巡检报告，绑定读取时返回的 snapshot_id 证据版本。仅写本机文件，不修改店铺。需要 write 令牌。",
        "inputSchema": _schema({"store_id": {"type": "string"}, "snapshot_id": {"type": "string"}, "title": {"type": "string", "maxLength": 200},
                                "markdown": {"type": "string", "maxLength": 200000}},
                               ["store_id", "snapshot_id", "title", "markdown"]),
        "scope": "write",
    },
    "ivyea_report_read": {
        "description": "按 report_id 读取已保存的本地巡检报告及其快照证据。",
        "inputSchema": _schema({"report_id": {"type": "string"}}, ["report_id"]),
        "scope": "read",
    },
    "ivyea_health": {
        "description": "store-ops 版本与集成开关状态。用于确认连接是否正常。",
        "inputSchema": _schema(),
        "scope": "read",
    },

}


def _rate_ok(token_id: str) -> bool:
    now = time.time()
    with _hits_lock:
        q = _hits.setdefault(token_id, deque())
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= _RATE_PER_MIN:
            return False
        q.append(now)
        return True


def _auth(request: Request, authorization: Optional[str], need: str = "read") -> dict:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    ip = request.client.host if request.client else ""
    row = mcp_tokens.verify(token, need=need, ip=ip)
    if not row:
        # 不区分"过期""不存在""scope 不够" —— 那个区别对攻击者有用，对正常用户没用。
        raise HTTPException(401, "无效的 MCP 令牌")
    if not _rate_ok(str(row["id"])):
        raise HTTPException(429, f"超过每分钟 {_RATE_PER_MIN} 次调用上限")
    return row


def _text(text: str, *, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _dump(obj: Any) -> dict:
    return _text(json.dumps(obj, ensure_ascii=False, default=str))


async def _call_tool(name: str, args: dict) -> dict:
    """执行一个工具，返回 MCP 的 content 结构。"""
    if name == "ivyea_emag_knowledge_search":
        if (not isinstance(args, dict) or set(args) - {"query", "limit"}
                or not isinstance(args.get("query"), str) or not args["query"].strip()
                or len(args["query"]) > 500 or type(args.get("limit", 5)) is not int
                or not 1 <= args.get("limit", 5) <= 20):
            return _text("Use a nonempty query up to 500 characters and a limit between 1 and 20", is_error=True)
        from app.services import emag_knowledge
        return _dump(emag_knowledge.search(args["query"], args.get("limit", 5)))
    if name == "ivyea_knowledge_search":
        if (not isinstance(args, dict) or set(args) - {"query", "limit"}
                or not isinstance(args.get("query"), str) or not args["query"].strip()
                or len(args["query"]) > 4000 or type(args.get("limit", 8)) is not int
                or not 1 <= args.get("limit", 8) <= 50):
            return _text("Use a nonempty query and a limit between 1 and 50", is_error=True)
        from app.services import ivyea_agent_service
        return _dump(ivyea_agent_service.knowledge_search(args["query"], limit=args.get("limit", 8)))
    if name == "ivyea_emag_clearance_review":
        if (not isinstance(args, dict) or set(args) - {"store_id", "baseline_snapshot_id"}
                or not isinstance(args.get('store_id'), str)
                or ('baseline_snapshot_id' in args and not isinstance(args['baseline_snapshot_id'], str))):
            return _text("Store and optional baseline must be strings; unexpected arguments are rejected", is_error=True)
        try:
            from app.services import emag_clearance_review
            return _dump(emag_clearance_review.read(args['store_id'], args.get('baseline_snapshot_id')))
        except (ValueError, OSError) as exc:
            return _text(str(exc), is_error=True)
    if name in {"ivyea_store_snapshot", "ivyea_report_save", "ivyea_report_read", "ivyea_emag_job_status"}:
        from app.services import store_artifacts as stores
        spec = TOOLS[name]["inputSchema"]
        if not isinstance(args, dict) or set(args) - set(spec["properties"]):
            return _text("Unexpected tool arguments", is_error=True)
        if any(not isinstance(args.get(key), str) for key in spec["required"]):
            return _text("Required arguments must be strings", is_error=True)
        try:
            if name == "ivyea_emag_job_status":
                from app.services import emag_jobs
                return _dump(emag_jobs.latest(args['store_id']))
            if name == "ivyea_store_snapshot":
                return _dump(stores.read_snapshot(args['store_id']))
            if name == "ivyea_report_read":
                return _dump(stores.read_report(args['report_id']))
            return _dump(stores.save_report(args['store_id'], args['snapshot_id'], args['title'], args['markdown']))
        except (ValueError, FileNotFoundError) as exc:
            return _text(str(exc), is_error=True)
    if name == "ivyea_health":
        from app.core.version import app_version
        from app.services import skill_market
        return _dump({"version": app_version(),
                      "skill_market_enabled": skill_market.market_enabled()})

    return _text(f"未知工具：{name}", is_error=True)


class RpcBody(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = None
    method: str
    params: Optional[dict] = None


@router.post("")
@router.post("/")
async def rpc(body: RpcBody, request: Request,
              authorization: Optional[str] = Header(None)):
    """MCP JSON-RPC 入口。"""
    method = body.method
    params = body.params or {}

    if method in ("initialize", "ping"):
        _auth(request, authorization)
        if method == "ping":
            return {"jsonrpc": "2.0", "id": body.id, "result": {}}
        return {"jsonrpc": "2.0", "id": body.id, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }}

    if method.startswith("notifications/"):
        _auth(request, authorization)
        return Response(status_code=202)

    if method == "tools/list":
        row = _auth(request, authorization)
        scopes = set((row.get("scopes") or "").split(","))
        # **只列这个令牌调得动的工具**。列出一个调用必然 401 的工具，
        # 对面的 Agent 只会反复重试然后给用户一个说不清的失败。
        return {"jsonrpc": "2.0", "id": body.id, "result": {
            "tools": [{"name": n, "description": t["description"],
                       "inputSchema": t["inputSchema"]}
                      for n, t in TOOLS.items() if t["scope"] in scopes],
        }}

    if method == "tools/call":
        name = str(params.get("name") or "")
        spec = TOOLS.get(name)
        if not spec:
            raise HTTPException(404, f"未知工具：{name}")
        # 按工具**各自声明的 scope** 校验，而不是入口处一刀切。
        row = _auth(request, authorization, need=spec["scope"])
        from app.core import audit
        audit.record("mcp", "tools/call", target=name, actor_name=str(row.get("name") or ""))
        try:
            return {"jsonrpc": "2.0", "id": body.id,
                    "result": await _call_tool(name, params.get("arguments") or {})}
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — 工具异常要变成 MCP 的错误结果而不是 500
            logger.exception("MCP 工具执行失败 %s", name)
            return {"jsonrpc": "2.0", "id": body.id,
                    "result": _text(f"{type(exc).__name__}: {exc}", is_error=True)}

    raise HTTPException(400, f"不支持的方法：{method}")
