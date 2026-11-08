"""Controlled IvyeaOps tool bridge for embedded IvyeaAgent chat.

The local IvyeaAgent process should not import or know IvyeaOps internals.
Instead, Ops exposes a short-lived, signed bridge token and this registry of
safe board actions. Each tool declares its board permission and parameter
schema; execution rehydrates the principal into ``current_user`` so existing
per-user storage and permission boundaries still apply.
"""
from __future__ import annotations

import inspect
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Union

from fastapi import HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core import permissions as module_permissions
from app.core.config import settings

_BRIDGE_SALT = "ivyea-ops.ivyea-agent.bridge"
_BRIDGE_MAX_AGE_SECONDS = 15 * 60
_serializer = URLSafeTimedSerializer(settings.secret_key, salt=_BRIDGE_SALT)


Handler = Callable[[dict[str, Any]], Union[Any, Awaitable[Any]]]


@dataclass(frozen=True)
class OpsTool:
    name: str
    module: str
    title: str
    description: str
    parameters: dict[str, Any]
    handler: Handler
    destructive: bool = False
    long_running: bool = False


def _principal() -> dict[str, Any]:
    from app.core.security import ADMIN_ID, current_user
    cu = current_user.get()
    if cu:
        return {
            "id": cu.get("id"),
            "role": cu.get("role", "user"),
            "email": cu.get("email", ""),
            "permissions": list(cu.get("permissions") or []),
            "position": cu.get("position", ""),
        }
    return {"id": ADMIN_ID, "role": "admin", "email": settings.admin_user, "permissions": []}


def issue_bridge_token() -> str:
    principal = _principal()
    return _serializer.dumps({"principal": principal, "iat": int(time.time())})


def principal_from_token(token: str) -> dict[str, Any]:
    try:
        data = _serializer.loads(token, max_age=_BRIDGE_MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        raise HTTPException(status_code=401, detail="IvyeaAgent bridge token expired") from exc
    except BadSignature as exc:
        raise HTTPException(status_code=401, detail="IvyeaAgent bridge token invalid") from exc
    principal = data.get("principal") if isinstance(data, dict) else None
    if not isinstance(principal, dict) or not principal.get("role"):
        raise HTTPException(status_code=401, detail="IvyeaAgent bridge token missing principal")
    return {
        "id": principal.get("id"),
        "role": principal.get("role", "user"),
        "email": principal.get("email", ""),
        "permissions": list(principal.get("permissions") or []),
        "position": principal.get("position", ""),
    }


def activate_bridge_principal(token: str) -> dict[str, Any]:
    from app.core.security import current_user
    principal = principal_from_token(token)
    current_user.set(principal)
    return principal


def _can_access(module: str, principal: dict[str, Any] | None = None) -> bool:
    principal = principal or _principal()
    if principal.get("role") == "admin":
        return True
    if module in module_permissions.BASE_MODULES:
        return True
    return module in (principal.get("permissions") or [])


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _limit(value: Any, max_chars: int = 24000) -> Any:
    text = json.dumps(_jsonable(value), ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return _jsonable(value)
    return {
        "truncated": True,
        "max_chars": max_chars,
        "preview": text[:max_chars],
    }


def _obj(**props: Any) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": []}


def _str(desc: str = "", default: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "string"}
    if desc:
        out["description"] = desc
    if default is not None:
        out["default"] = default
    return out


def _int(desc: str = "", default: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "integer"}
    if desc:
        out["description"] = desc
    if default is not None:
        out["default"] = default
    return out




















def _arr(item: dict[str, Any], desc: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {"type": "array", "items": item}
    if desc:
        out["description"] = desc
    return out


async def _image_generate(args: dict[str, Any]) -> Any:
    """作图。**这是个长任务**：提交后返回 task_id，由 agent 自己轮询状态。

    为什么要把它做成工具：工作台已经有一条配好的作图链路（系统配置 → AI 生图），
    但它只挂在「AI 作图」那个页面上 —— 用户在任务台说"给我画一张主图"，
    agent 手里没有任何手段去调它，只能回一句"我做不到"。而这条链路本来就在
    这台机器上配好了。
    """
    from app.routers import assistant

    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    refs = [u for u in (args.get("image_urls") or []) if isinstance(u, str) and u.strip()]
    req = assistant.ImageReq(
        prompt=prompt,
        size=str(args.get("size") or "1024x1024"),
        n=max(1, min(int(args.get("n") or 1), 4)),
        image_urls=refs or None,
    )
    out = await assistant.image_submit(req)
    return {**out, "note": "已提交作图任务。用 image_status 查询进度，通常十几秒到一分钟。"}


async def _image_status(args: dict[str, Any]) -> Any:
    from app.routers import assistant
    task_id = str(args.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("task_id is required")
    return await assistant.image_status(task_id)


def _show_image_roots() -> list[Path]:
    """`show_image` 允许读取的目录。

    **就是"工作区绑的目录"，不另发明一套授权。** 给工作区绑目录本来就是这套系统里
    管 Agent 文件访问面的那个授权动作（仅限管理员，见 console_sessions.create_workspace
    的注释：和 MCP 的 stdio command 是同一类）。这里复用它，等于"Agent 能读写的地方
    就是它能给你看图的地方" —— 没有新增任何访问面。

    没绑目录的工作区（比如默认工作区）不在这里面：那种情况下 Agent 用的是自己的
    进程 cwd，而那是个 ops 无从知道、也从没被授权过的目录。宁可让工具报一句
    "去给工作区绑个目录"，也不能自己猜一个路径就放行。
    """
    from app.services import console_sessions
    principal = _principal()
    email = str(principal.get("email") or principal.get("id") or "")
    roots: list[Path] = []
    for ws in console_sessions.list_workspaces(email, principal.get("role") == "admin"):
        raw = str(ws.get("path") or "").strip()
        if not raw:
            continue
        try:
            roots.append(Path(raw).expanduser().resolve())
        except OSError:
            continue
    return roots


def _show_image(args: dict[str, Any]) -> Any:
    """把工作区里的一张图放进回答，让用户在网页上直接看见。

    图片本体**不进模型**（和用户贴图那条路一样）：ops 把文件复制进会话图库、换一个
    站内地址回给模型，模型只要把 `![](地址)` 写进正文，前端就渲染成图。
    """
    from app.routers import assistant

    raw_path = str(args.get("path") or "").strip()
    if not raw_path:
        raise ValueError("path is required")
    roots = _show_image_roots()
    if not roots:
        raise ValueError(
            "还没有任何工作区绑定了目录，所以没有可以读图的地方。"
            "请在「任务台 → 工作区」给工作区绑一个目录（需要管理员），再试。")
    try:
        target = Path(raw_path).expanduser().resolve()
    except OSError as exc:
        raise ValueError(f"路径解不开：{exc}") from exc
    # resolve() 已经把符号链接展开了，所以这个包含判断连"软链接指到工作区外面"
    # 一起堵住 —— 只比字符串前缀的话，工作区里放一条指向 /etc 的软链就穿过去了。
    if not any(target == r or r in target.parents for r in roots):
        raise ValueError(
            f"{target} 不在任何已绑定的工作区目录里，不能展示。"
            f"当前允许：{'、'.join(str(r) for r in roots)}")
    if not target.is_file():
        raise ValueError(f"{target} 不是一个文件（或不存在）")
    try:
        data = target.read_bytes()
    except OSError as exc:
        raise ValueError(f"读不了这个文件：{exc}") from exc
    url, size = assistant.store_session_image(data)     # 大小/魔数校验都在里面
    return {
        "url": url,
        "bytes": size,
        "caption": str(args.get("caption") or "").strip(),
        "note": f"图片已就绪。**把 `![{args.get('caption') or '图片'}]({url})` 原样写进你的回答正文**，"
                "用户才看得到它；只说「图在这里」是看不见的。地址会跟着会话存档留下来。",
    }














































async def _monitor_snapshot(args: dict[str, Any]) -> Any:
    from app.routers import monitor
    return monitor.snapshot(_user="bridge")


async def _monitor_services(args: dict[str, Any]) -> Any:
    from app.routers import monitor
    return monitor.services(_user="bridge")


async def _monitor_token_usage(args: dict[str, Any]) -> Any:
    from app.routers import monitor
    return monitor.token_usage(_user="bridge")


async def _skill_tools_list(args: dict[str, Any]) -> Any:
    from app.routers import skill_tools
    return skill_tools.list_tools(
        q=str(args.get("query") or ""),
        category=str(args.get("category") or ""),
        limit=int(args.get("limit") or 30),
    )




















TOOLS: tuple[OpsTool, ...] = (
    OpsTool("image_generate", "tools", "AI 作图",
            "按提示词生成图片（也可传参考图做图生图）。**用户提出任何作图/出图/"
            "画一张/生成主图之类的需求时用它** —— 这台机器上已经配好了生图链路。"
            "返回 task_id，再用 image_status 查结果。", _obj(
                prompt=_str("画面描述，越具体越好；中文英文都行"),
                size=_str("尺寸，如 1024x1024 / 1024x1536", default="1024x1024"),
                n=_int("生成张数，1-4", default=1),
                image_urls=_arr(_str(), "原图（给了就是图生图/改图，会保留原图内容）。"
                                        "用户附图时系统会给你一个 ivyea-ref:// 句柄，"
                                        "原样填进来即可；也接受 http(s) 图片地址，"
                                        "比如上一轮出的图 —— 那就是在它基础上继续改")),
            _image_generate, long_running=True),
    OpsTool("image_status", "tools", "作图任务状态",
            "查询 image_generate 提交的任务，完成后返回图片地址。", _obj(
                task_id=_str("image_generate 返回的任务 ID")),
            _image_status),
    OpsTool("show_image", "tools", "给用户看图",
            "把工作区里的一张图片**展示给用户**。你自己截的图、跑出来的图表、"
            "读到的产品图，想让用户亲眼看看就用它 —— 光用文字描述用户是看不见的。"
            "返回一个站内地址，你必须把 `![说明](地址)` 写进回答正文，网页上才会渲染成图。"
            "只能读已绑定目录的工作区里的文件。（作图请用 image_generate，这个工具只负责展示已有文件。）",
            _obj(
                path=_str("图片文件路径，要在某个已绑定目录的工作区里"),
                caption=_str("一句话说明，会变成图的 alt 文字")),
            _show_image),
    OpsTool("monitor_snapshot", "servmon", "服务器快照", "读取 CPU、内存、磁盘、网络快照。", _obj(), _monitor_snapshot),
    OpsTool("monitor_services", "servmon", "服务状态", "读取服务器监控中的 systemd 服务状态。", _obj(), _monitor_services),
    OpsTool("monitor_token_usage", "servmon", "Token 用量", "读取 Token 用量和模型成本概览。", _obj(), _monitor_token_usage),
    OpsTool("skill_tools_list", "skill-hub", "Skill 工具列表", "列出 Skill Tools 板块可运行工具。", _obj(query=_str("搜索词"), category=_str("分类"), limit=_int(default=30)), _skill_tools_list),
)

_TOOL_BY_NAME = {tool.name: tool for tool in TOOLS}


def _public_tool(tool: OpsTool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "module": tool.module,
        "title": tool.title,
        "description": tool.description,
        "parameters": tool.parameters,
        "destructive": tool.destructive,
        "long_running": tool.long_running,
    }


def list_tools(module: str = "", query: str = "", principal: dict[str, Any] | None = None) -> dict[str, Any]:
    module = (module or "").strip()
    q = (query or "").strip().lower()
    principal = principal or _principal()
    rows: list[dict[str, Any]] = []
    for tool in TOOLS:
        if module and tool.module != module:
            continue
        if not _can_access(tool.module, principal):
            continue
        haystack = f"{tool.name} {tool.module} {tool.title} {tool.description}".lower()
        # **按词匹配，不是整串匹配。** 原来是 `q not in haystack`，于是 agent 很自然地
        # 打一串关键词（"图片 状态 image status"）时必定返回空 —— 实测它因此
        # 连着换了 5 种问法才找到工具，白烧好几轮。任一词命中即返回，宁可多给几个。
        if q and not any(w in haystack for w in q.split()):
            continue
        rows.append(_public_tool(tool))
    return {
        "ok": True,
        "tools": rows,
        "modules": sorted({row["module"] for row in rows}),
        "principal": {"role": principal.get("role"), "email": principal.get("email", "")},
    }


async def call_tool(name: str, arguments: dict[str, Any] | None = None, principal: dict[str, Any] | None = None) -> dict[str, Any]:
    tool = _TOOL_BY_NAME.get((name or "").strip())
    if not tool:
        return {"ok": False, "error": "tool_not_found", "tool": name}
    principal = principal or _principal()
    if not _can_access(tool.module, principal):
        return {"ok": False, "error": "permission_denied", "tool": tool.name, "module": tool.module}
    args = arguments if isinstance(arguments, dict) else {}
    try:
        result = tool.handler(args)
        if inspect.isawaitable(result):
            result = await result
    except HTTPException as exc:
        return {"ok": False, "error": "http_error", "status_code": exc.status_code, "detail": exc.detail, "tool": tool.name}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "tool_error", "detail": str(exc), "tool": tool.name}
    return {
        "ok": True,
        "tool": _public_tool(tool),
        "result": _limit(result),
    }
