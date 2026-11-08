"""AI synthesis with fallback chain.

Priority:
  1. deepseek  (DeepSeek-chat via HTTP streaming — true token-by-token)
  2. apimart   (Claude via HTTP streaming)
  3. Hermes CLI
  4. Codex CLI
  5. Claude CLI

Shared text and image generation for current application workflows.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict

import httpx

from app.core.proc import no_window_kwargs
from app.services.runners import _build_runner_cmd, _find_bin, build_child_env

logger = logging.getLogger("ivyea.services.ai_synthesis_service")

_log = logging.getLogger(__name__)

# In-memory observability: last N text-chain calls, surfaced in 系统配置 →
# 「最近 AI 调用」 so admins can see which provider answered without journald.
_AI_CALL_LOG: "deque[dict[str, Any]]" = deque(maxlen=50)


def record_ai_call(provider: str, ok: bool, *, chars: int = 0,
                   failures: list[str] | None = None, kind: str = "text") -> None:
    _AI_CALL_LOG.appendleft({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "provider": provider,
        "ok": ok,
        "chars": chars,
        "kind": kind,
        "failures": list(failures or []),
    })


def recent_ai_calls(limit: int = 50) -> list[dict[str, Any]]:
    return list(_AI_CALL_LOG)[:limit]


def _apimart_key() -> str:
    """Return the configured Apimart key, or '' if unset. No hardcoded
    fallback — past attempts to ship a 'shared' key got banned upstream."""
    from app.core import hub_settings
    val = hub_settings.get("apimart_key")
    return str(val) if val else ""


def _apimart_base() -> str:
    from app.core import hub_settings
    val = hub_settings.get("apimart_base")
    return str(val) if val else "https://api.apimart.ai/v1"


def _read_hermes_env() -> Dict[str, str]:
    """Parse ~/.hermes/.env and return its key=value pairs."""
    result: Dict[str, str] = {}
    try:
        text = (Path.home() / ".hermes" / ".env").read_text(errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    except Exception:
        logger.debug("text = 失败（旁路，已忽略）", exc_info=True)
    return result


def _deepseek_key() -> str:
    """Return DeepSeek API key from hub_settings, falling back to ~/.hermes/.env."""
    from app.core import hub_settings
    val = hub_settings.get("deepseek_api_key")
    if val:
        return str(val)
    return _read_hermes_env().get("DEEPSEEK_API_KEY", "")


# "assistant" == the global fallback text model (the AI 问答 slot, assistant_*).
# It is a user-configured OpenAI-compatible / anthropic HTTP endpoint, so it is
# safe for non-admin users and acts as the standard chain's fallback step.
# NOTE: apimart is IMAGE-GEN ONLY (no text/chat endpoint) — it must NOT appear
# in any text chain; calling its /v1/messages returns 403.
# 2026-08-06：hermes 从文本链候选中移除。旧配置里残留的 "hermes" 会在
# _text_provider_chain() 里被静默过滤掉，不会报错、也不会再被自动调用。
_VALID_TEXT_PROVIDERS = ("ivyea-agent", "codex", "claude", "deepseek", "assistant")


# Providers safe for non-admin users: pure HTTP APIs, no local CLI / shell / MCP.
_HTTP_ONLY_PROVIDERS = ("ivyea-agent", "deepseek", "assistant")


def _text_provider_chain() -> list[str]:
    """Parse the comma-separated text_ai_providers setting and filter to
    known names. Empty / malformed config falls back to the built-in-safe order.

    SECURITY: for non-admin users, the chain is forced to HTTP-only providers
    (deepseek / apimart) so a user request can NEVER spawn a local CLI agent
    (codex/claude) with shell / MCP / filesystem access."""
    from app.core import hub_settings
    # Standard chain: IvyeaAgent first, then HTTP DeepSeek / global fallback,
    # then optional external CLI agents. Hermes is no longer part of any
    # automatic chain (2026-08-06) — it stays available only where the user
    # picks a provider by hand in the /agents board.
    raw = str(hub_settings.get("text_ai_providers") or "").strip()
    if not raw:
        chain = ["ivyea-agent", "deepseek", "assistant", "codex", "claude"]
    else:
        out: list[str] = []
        for p in raw.split(","):
            p = p.strip().lower()
            if p in _VALID_TEXT_PROVIDERS and p not in out:
                out.append(p)
        chain = out or ["ivyea-agent", "deepseek", "assistant", "codex", "claude"]

    # IvyeaAgent is the default brain everywhere: lead with it regardless of the
    # configured order (graceful fallback to the rest if it's down). The panel
    # bridge passes skip_agent=True to drop it and avoid agent→ops→agent nesting.
    def _lead_with_agent(c: list[str]) -> list[str]:
        return ["ivyea-agent"] + [p for p in c if p != "ivyea-agent"]

    # Non-admin (and only when a request context is set) → HTTP-only, with the
    # global fallback model after the agent (HTTP-safe, no local CLI/MCP/shell).
    try:
        from app.core.security import current_user
        cu = current_user.get()
        if cu is not None and cu.get("role") != "admin":
            http = [p for p in chain if p in _HTTP_ONLY_PROVIDERS]
            return _lead_with_agent(http or ["assistant", "deepseek"])
    except Exception:
        logger.debug("current_user.get 失败（旁路，已忽略）", exc_info=True)
    return _lead_with_agent(chain)

_ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

async def _stream_apimart(prompt: str) -> AsyncGenerator[str, None]:
    """Stream text tokens from apimart (Claude HTTP streaming)."""
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=30)) as client:
        async with client.stream(
            "POST",
            f"{_apimart_base()}/messages",
            json=payload,
            headers={
                "Authorization": f"Bearer {_apimart_key()}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                except Exception:
                    continue
                evt_type = event.get("type", "")
                if evt_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            yield text
                elif evt_type == "error":
                    raise RuntimeError(f"apimart error: {event.get('error', event)}")


async def generate_text(prompt: str, skip_agent: bool = False,
                        inject_retrieval: bool = True) -> str:
    """Plain text generation without tools.

    For tasks that just need the model to write text (e.g. authoring a
    SKILL.md from a description). Tries IvyeaAgent / configured HTTP models first,
    then configured CLI fallbacks.
    """
    failures: list[str] = []

    if not skip_agent and "ivyea-agent" in _text_provider_chain():
        try:
            parts: list[str] = []
            # inject_retrieval=False 给的是**要被机器读的输出**（标题、JSON）：
            # 开着检索注入时 agent 会在正文后面缀上 [K1] 之类的引用标记，
            # 一条 14 字的标题能被它顶掉三分之一（实测起出来的名字末尾挂着 "[K2"）。
            async for chunk in _stream_ivyea_agent(prompt, inject_retrieval=inject_retrieval):
                parts.append(chunk)
            text = "".join(parts).strip()
            if text:
                return text
            failures.append("IvyeaAgent 返回空")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"IvyeaAgent: {exc}")

    if "assistant" in _text_provider_chain() and assistant_text_cfg().get("api_key"):
        try:
            parts = []
            async for chunk in stream_assistant_prompt(prompt):
                parts.append(chunk)
            text = "".join(parts).strip()
            if text:
                return text
            failures.append("全局兜底大模型返回空")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"全局兜底大模型: {exc}")

    dkey = _deepseek_key()
    if dkey:
        try:
            parts: list[str] = []
            async for chunk in _stream_openai_compat(
                dkey, "https://api.deepseek.com", "deepseek-chat", prompt
            ):
                parts.append(chunk)
            text = "".join(parts).strip()
            if text:
                return text
            failures.append("DeepSeek 返回空")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"DeepSeek: {exc}")

    if _apimart_key():
        try:
            parts = []
            async for chunk in _stream_apimart(prompt):
                parts.append(chunk)
            text = "".join(parts).strip()
            if text:
                return text
            failures.append("Apimart 返回空")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"Apimart: {exc}")

    # Global fallback model (assistant slot) — last-resort HTTP provider so any
    # text task degrades gracefully even when deepseek/apimart are unavailable.
    if assistant_text_cfg().get("api_key"):
        try:
            parts = []
            async for chunk in stream_assistant_prompt(prompt):
                parts.append(chunk)
            text = "".join(parts).strip()
            if text:
                return text
            failures.append("全局兜底大模型返回空")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"全局兜底大模型: {exc}")

    raise RuntimeError(
        "无可用文本模型。" + (" / ".join(failures) if failures else
        "请在「系统配置」配置 IvyeaAgent / 全局兜底大模型 / DeepSeek。")
    )


async def generate_text_provider(provider: str, prompt: str) -> str:
    """Generate text via a SPECIFIC safe provider.

    Raises if that provider isn't configured/usable — caller can fall back. Used
    for heterogeneous multi-model review (different personas → different models).
    """
    provider = (provider or "").lower().strip()
    if provider == "ivyea-agent":
        parts: list[str] = []
        async for chunk in _stream_ivyea_agent(prompt):
            parts.append(chunk)
        text = "".join(parts).strip()
        if not text:
            raise RuntimeError("IvyeaAgent 返回空")
        return text
    if provider == "assistant":
        if not assistant_text_cfg().get("api_key"):
            raise RuntimeError("全局兜底大模型未配置")
        parts = []
        async for chunk in stream_assistant_prompt(prompt):
            parts.append(chunk)
        text = "".join(parts).strip()
        if not text:
            raise RuntimeError("全局兜底大模型返回空")
        return text
    if provider == "deepseek":
        dkey = _deepseek_key()
        if not dkey:
            raise RuntimeError("DeepSeek 未配置")
        parts: list[str] = []
        async for chunk in _stream_openai_compat(dkey, "https://api.deepseek.com", "deepseek-chat", prompt):
            parts.append(chunk)
        text = "".join(parts).strip()
        if not text:
            raise RuntimeError("DeepSeek 返回空")
        return text
    if provider == "apimart":
        if not _apimart_key():
            raise RuntimeError("Apimart 未配置")
        parts = []
        async for chunk in _stream_apimart(prompt):
            parts.append(chunk)
        text = "".join(parts).strip()
        if not text:
            raise RuntimeError("Apimart 返回空")
        return text
    raise RuntimeError(f"未知 provider: {provider}")


async def generate_openai_compat(base_url: str, api_key: str, model: str, prompt: str) -> str:
    """Generate text via any OpenAI-compatible endpoint (custom model slots)."""
    if not (base_url and model):
        raise RuntimeError("自定义模型缺少 base_url/model")
    parts: list[str] = []
    async for chunk in _stream_openai_compat(api_key or "", base_url.rstrip("/"), model, prompt):
        parts.append(chunk)
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("自定义模型返回空")
    return text


# ---------------------------------------------------------------------------
# Global fallback text model ("assistant" slot) — also powers the AI 问答 panel.
# This is the canonical home; app.routers.assistant imports from here (DRY).
# ---------------------------------------------------------------------------

# OpenAI-compatible base URLs per provider name, for when base_url is left blank.
ASSISTANT_PROVIDER_BASE = {
    "deepseek":   "https://api.deepseek.com",
    "openai":     "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "dashscope":  "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu":      "https://open.bigmodel.cn/api/paas/v4",
    # GLM Coding Plan（订阅）走的是**另一个地址**：官方明确要求 coding 专用端点
    # /api/coding/paas/v4，填成上面那个通用端点不通，而报错完全指不到"地址错了"上。
    "zai-coding":  "https://api.z.ai/api/coding/paas/v4",
    "glm-coding":  "https://open.bigmodel.cn/api/coding/paas/v4",
    # Kimi Code 订阅（授权登录后用）。
    "kimi-code":   "https://api.kimi.com/coding/v1",
    "groq":       "https://api.groq.com/openai/v1",
    "together":   "https://api.together.xyz/v1",
    "xiaomi":     "https://token-plan-sgp.xiaomimimo.com/v1",
    "kimi":       "https://api.kimi.com/coding/v1",
}


def has_text_provider() -> bool:
    """True when at least one text provider (IvyeaAgent / DeepSeek / Apimart / global
    fallback model) is configured — i.e. ``generate_text`` can answer even when
    no local agent CLI (IvyeaAgent/Codex/Claude) is installed."""
    try:
        from app.services import ivyea_agent_service as ivyea
        return bool(
            ivyea.availability().get("available")
            or _deepseek_key()
            or _apimart_key()
            or assistant_text_cfg().get("api_key")
        )
    except Exception:  # noqa: BLE001
        return False


def assistant_text_cfg() -> dict:
    """The global fallback text model (== AI 问答 assistant slot), or {} if the
    user hasn't configured one. Keys: provider / model / api_key / base_url."""
    from app.core import hub_settings
    provider = str(hub_settings.get("assistant_provider") or "").strip()
    if not provider:
        return {}
    return {
        "provider": provider,
        "model":    str(hub_settings.get("assistant_model") or "").strip(),
        "api_key":  str(hub_settings.get("assistant_api_key") or "").strip(),
        "base_url": str(hub_settings.get("assistant_base_url") or "").strip(),
    }


async def stream_assistant_prompt(prompt: str) -> AsyncGenerator[str, None]:
    """Stream a single-prompt completion from the global fallback slot.

    Handles anthropic-native and OpenAI-compatible providers, mirroring the
    AI 问答 panel's behaviour so the two never diverge. Raises if unconfigured.
    """
    cfg = assistant_text_cfg()
    if not cfg:
        raise RuntimeError("全局兜底大模型未配置（系统配置 → 全局兜底大模型）")
    provider = cfg["provider"]
    key = cfg["api_key"]
    if not key:
        raise RuntimeError(f"{provider} key 未配置")

    if provider == "anthropic":
        base = (cfg["base_url"] or "https://api.anthropic.com/v1").rstrip("/")
        payload = {
            "model": cfg["model"] or "claude-sonnet-4-6",
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=30)) as c:
            async with c.stream(
                "POST", f"{base}/messages", json=payload,
                headers={"Authorization": f"Bearer {key}", "anthropic-version": "2023-06-01"},
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        ev = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    if ev.get("type") == "content_block_delta":
                        t = ev.get("delta", {}).get("text", "")
                        if t:
                            yield t
        return

    base = cfg["base_url"] or ASSISTANT_PROVIDER_BASE.get(provider, "")
    if not base:
        raise RuntimeError(f"{provider} 需要填写 Base URL")
    if not cfg["model"]:
        raise RuntimeError(f"{provider} 需要填写模型名")
    async for chunk in _stream_openai_compat(key, base.rstrip("/"), cfg["model"], prompt):
        yield chunk


async def _try_assistant(prompt: str, failures: list[str]) -> AsyncGenerator[tuple[str, str], None]:
    """Chain step for the global fallback model — same contract as _try_deepseek."""
    yield "_attempt", "assistant"
    if not assistant_text_cfg().get("api_key"):
        failures.append(
            "全局兜底大模型未配置 — 在「系统配置 → 全局兜底大模型」填写 provider / model / key"
        )
        return
    try:
        got = False
        async for chunk in stream_assistant_prompt(prompt):
            got = True
            yield "assistant", chunk
        if not got:
            failures.append("全局兜底大模型返回空")
        return
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        body = ""
        try:
            body = exc.response.text[:200] if exc.response is not None else ""
        except Exception:
            logger.debug("body = exc.response.text 失败（旁路，已忽略）", exc_info=True)
        failures.append(f"全局兜底模型 HTTP {code}：{body or '请求失败'}")
        _log.warning("assistant fallback failed: HTTP %s — %s", code, body)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"全局兜底模型调用失败：{exc}")
        _log.warning("assistant fallback failed: %s", exc)


async def _stream_ivyea_agent(
    prompt: str,
    *,
    inject_retrieval: bool = True,
    use_tools: bool = False,
    plan_mode: bool = True,
    max_steps: int = 3,
    system: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream text from the embedded IvyeaAgent service.

    ``inject_retrieval=False`` is for structured-output tasks (strict JSON):
    retrieval injection makes the agent append 引用说明/[K1] citation markers
    that corrupt machine-parsed responses.

    ``use_tools=False`` (the default) runs the turn with no tool schemas at all.
    Every caller here hands the agent the material it needs and wants prose or
    JSON back — with tools attached the agent instead spends its steps hunting
    for data (and in plan_mode it is refused anyway), and that narration streams
    straight into the panel as if it were the report.

    """
    from app.services import ivyea_agent_service as ivyea

    status = await asyncio.to_thread(ivyea.ensure_available)
    if not status.get("available"):
        raise RuntimeError(status.get("error") or "IvyeaAgent 服务未连接")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    token = ivyea._token()  # same bridge auth path; secret never leaves backend
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {
        "message": prompt,
        "max_steps": max_steps,
        "use_tools": use_tools,
        "plan_mode": plan_mode,
        # persist=False — this is IvyeaOps' internal text engine (report/analysis/
        # ingest cleaning), not a user chat. Persisting would spam the shared
        # agent session history that the dock and workbench chat now both read.
        "persist": False,
        "inject_retrieval": inject_retrieval,
        # We consume the token stream and ignore the agent's `final` event, so a
        # superseded draft can never be taken back. The citation gate makes the
        # model rewrite the whole answer with [K#] markers — without this we
        # streamed both copies and the panel showed the report twice.
        "defer_citation_text": True,
        "system": system or (
            "你正在作为 IvyeaOps 的内置文本生成引擎。"
            "直接基于输入数据生成最终成品，不要输出查数据/找工具一类的过程叙述。"
        ),
    }
    got_token = False
    final_text = ""
    event = "message"
    # 纯文本生成 300s 够用；带工具的原生取数要先跑一串 MCP 调用再写报告，
    # 沿用 hermes 时代给这条路径的 600s（当时就是被 MCP 往返拖长才加的）。
    read_timeout = 600 if use_tools else 300
    async with httpx.AsyncClient(timeout=httpx.Timeout(read_timeout, connect=30)) as client:
        async with client.stream("POST", f"{ivyea.base_url()}/v1/chat/stream", json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line:
                    event = "message"
                    continue
                if line.startswith("event:"):
                    event = line[6:].strip() or "message"
                    continue
                if not line.startswith("data:"):
                    continue
                try:
                    data = json.loads(line[5:].strip() or "{}")
                except Exception:
                    continue
                if event == "token":
                    text = str(data.get("text") or "")
                    if text:
                        got_token = True
                        yield text
                elif event == "final":
                    final_text = str(data.get("text") or "")
                elif event == "error":
                    raise RuntimeError(str(data.get("detail") or data.get("error") or data))
    if not got_token and final_text:
        yield final_text






async def _try_ivyea_agent(
    prompt: str, failures: list[str], *, inject_retrieval: bool = True
) -> AsyncGenerator[tuple[str, str], None]:
    yield "_attempt", "ivyea-agent"
    try:
        got = False
        async for chunk in _stream_ivyea_agent(prompt, inject_retrieval=inject_retrieval):
            got = True
            yield "ivyea-agent", chunk
        if not got:
            failures.append("IvyeaAgent 返回空")
        return
    except Exception as exc:  # noqa: BLE001
        failures.append(f"IvyeaAgent 调用失败：{exc}")
        _log.warning("ivyea-agent failed: %s", exc)


# ---------------------------------------------------------------------------
# Vision provider helpers
# ---------------------------------------------------------------------------

def _openai_key() -> str:
    from app.core import hub_settings
    val = hub_settings.get("openai_api_key")
    return str(val) if val else ""


_VISION_CAPABLE_PROVIDERS = ("openai", "anthropic", "openrouter", "google", "together",
                             "custom", "apimart", "deepseek",
                             "siliconflow", "dashscope", "zhipu")


def _assistant_vision_cfg() -> tuple[str, str, str, str] | None:
    """Return (provider, key, base_url, model) for the configured vision
    reviewer, or None.

    独立视觉复核槽（vision_provider/vision_api_key/vision_base_url/vision_model）
    优先——它与全局兜底彻底解耦，支持"文本兜底用 A 家、看图用 B 家"。
    未配置时回退旧行为：全局兜底槽 + assistant_vision_model（或 assistant_model），
    这样 2026-07 之前按 configuration.md 配置的用户无需迁移。
    Base URL 为空时按 provider 预设解析（openrouter 等网关需要完整模型 slug，
    不能再写死 gpt-4o）。"""
    from app.core import hub_settings

    def _resolve(provider: str, key: str, base: str, model: str):
        provider = provider.lower().strip()
        if not key or provider not in _VISION_CAPABLE_PROVIDERS:
            return None
        base = base.strip() or ASSISTANT_PROVIDER_BASE.get(provider, "")
        return provider, key, base, model.strip()

    independent = _resolve(
        str(hub_settings.get("vision_provider") or ""),
        str(hub_settings.get("vision_api_key") or ""),
        str(hub_settings.get("vision_base_url") or ""),
        str(hub_settings.get("vision_model") or ""),
    )
    if independent:
        return independent
    return _resolve(
        str(hub_settings.get("assistant_provider") or ""),
        str(hub_settings.get("assistant_api_key") or ""),
        str(hub_settings.get("assistant_base_url") or ""),
        str(hub_settings.get("assistant_vision_model")
            or hub_settings.get("assistant_model") or ""),
    )


_VISION_CHAIN_CACHE: tuple[float, dict] = (0.0, {})
# 缓存窗口。取 5 秒是因为它只需要覆盖**一次请求内部的扇出**：
# _vision_provider_chain / vision_tier / vision_tier_label 会连环调这个函数，
# 不缓存的话一次设置页刷新就是五六个 HTTP 往返（每个还带 2 秒超时）。
# 窗口再长就会让"刚配好视觉模型"的用户刷新后仍看到旧档位。
_VISION_CHAIN_TTL = 5.0


def _agent_vision_chain(*, fresh: bool = False) -> dict:
    """agent 自报的视觉三档链状态（/health 的 vision_chain）。

    老版本 serve 没有这个字段，回 {} —— 调用方要按"老行为"处理，
    不能把缺字段当成"没有视觉"。
    """
    global _VISION_CHAIN_CACHE
    now = time.monotonic()
    if not fresh:
        stamp, cached = _VISION_CHAIN_CACHE
        if now - stamp < _VISION_CHAIN_TTL:
            return cached
    try:
        from app.services import ivyea_agent_service as ivyea
        avail = ivyea.availability()
        chain = (avail.get("health") or {}).get("vision_chain") if avail.get("available") else None
        result = chain if isinstance(chain, dict) else {}
    except Exception:
        result = {}
    _VISION_CHAIN_CACHE = (now, result)
    return result


def _ivyea_agent_vision_available() -> bool:
    """ivyea-agent 能不能接带图任务。

    **看整条链，不是看主脑。** agent v1.13 起内部有三档降级：
      T1 主脑自带视觉 / T2 第三方视觉模型旁路代读 / T3 本地 CV+OCR 量化。
    此前这里只读 `model.capabilities.vision`（主脑那一档），于是用户主脑一旦是
    DeepSeek 这类纯文本模型，整条视觉链就被判死，Listing 的图片分析静默空转。

    老版本 serve 没有 vision_chain → 退回旧判据（只有主脑有视觉才算数），
    行为与升级前完全一致，不会把老 agent 判成能力更强。
    """
    chain = _agent_vision_chain()
    if chain:
        return bool(chain.get("effective"))
    try:
        from app.services import ivyea_agent_service as ivyea
        avail = ivyea.availability()
        if not avail.get("available"):
            return False
        caps = (((avail.get("health") or {}).get("model") or {}).get("capabilities") or {})
        return bool(caps.get("vision"))
    except Exception:
        return False


def vision_tier() -> int:
    """当前实际生效的视觉档位：1 主脑直读 / 2 旁路 / 3 本地 CV / 0 无。

    Listing 要靠它决定哪些分析做得了、哪些必须明说"跳过"——CV 能量化的
    （合规/比例/占比/配色/文字）照做，语义类的（版式逆向、审美）在 T3 下
    做不了就不要产出假结果。

    只有 agent 那一档能自报档位；走 openai / assistant 直连视觉模型时，
    那本来就是真视觉模型，等价于 T1。
    """
    chain = _vision_provider_chain()
    if not chain:
        return 0
    if chain[0] == "ivyea-agent":
        tier = _agent_vision_chain().get("tier")
        if isinstance(tier, int) and tier > 0:
            return tier
        return 1        # 老 serve：能进链就说明主脑有视觉
    return 1


def vision_tier_label() -> str:
    labels = {1: "主脑直读", 2: "视觉旁路", 3: "本地 CV 度量", 0: "无视觉能力"}
    tier = vision_tier()
    base = labels.get(tier, "未知")
    if tier == 2:
        model = ((_agent_vision_chain().get("sidecar") or {}).get("model") or "").strip()
        return f"{base} · {model}" if model else base
    if tier == 3:
        ocr = ((_agent_vision_chain().get("local_cv") or {}).get("ocr_engine") or "").strip()
        return f"{base}（OCR：{ocr}）" if ocr else f"{base}（无 OCR）"
    return base


def _vision_provider_chain() -> list[str]:
    """Parse vision_ai_providers setting; filter to providers that actually
    have a key configured in the current environment."""
    from app.core import hub_settings
    raw = str(hub_settings.get("vision_ai_providers") or "").strip()
    # apimart is image-GEN only (no vision/analysis), so it is NOT a vision
    # provider — image understanding needs a real vision model (ivyea-agent /
    # openai / the vision-capable global fallback).
    valid = ("ivyea-agent", "openai", "assistant")
    order = [p.strip().lower() for p in (raw or "ivyea-agent,openai,assistant").split(",")
             if p.strip().lower() in valid]
    order = list(dict.fromkeys(order)) or ["ivyea-agent", "openai", "assistant"]
    # 用户配置里没提 ivyea-agent 的旧配置也自动获得 agent 视觉（排最前，与文本链
    # 一致：agent 是本产品的一等 provider）。
    if "ivyea-agent" not in order:
        order.insert(0, "ivyea-agent")

    # Only keep providers that have credentials configured right now.
    available = []
    for p in order:
        if p == "ivyea-agent" and _ivyea_agent_vision_available():
            available.append(p)
        elif p == "openai" and _openai_key():
            available.append(p)
        elif p == "assistant" and _assistant_vision_cfg():
            available.append(p)

    # agent 恒排第一是**文本链**的规矩，视觉链不能照抄：agent 只在 T3（本地 CV
    # 量化）时，它给的是读数而不是画面，而 openai/assistant 槽里坐着的是真视觉
    # 模型。让 T3 顶掉真视觉模型是纯粹的质量倒退，所以这里把"只有 T3 的 agent"
    # 降到真视觉 provider 之后——它仍在链上，作为真视觉模型全挂时的兜底。
    if len(available) > 1 and available[0] == "ivyea-agent":
        if _agent_vision_chain().get("tier") == 3:
            available = available[1:] + ["ivyea-agent"]
    return available


def has_vision_capability() -> bool:
    """True if at least one vision provider is currently configured."""
    return bool(_vision_provider_chain())


async def _stream_apimart_vision(prompt: str, images_b64: list[str]) -> AsyncGenerator[str, None]:
    """Claude Vision via Apimart (Anthropic messages format)."""
    content: list[dict] = []
    for uri in images_b64[:4]:
        try:
            header, data = uri.split(",", 1)
            media_type = header.split(":")[1].split(";")[0]
        except (ValueError, IndexError):
            continue
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
    content.append({"type": "text", "text": prompt})

    payload = {"model": "claude-sonnet-4-6", "max_tokens": 8192,
               "messages": [{"role": "user", "content": content}], "stream": True}
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=30)) as client:
        async with client.stream(
            "POST", f"{_apimart_base()}/messages", json=payload,
            headers={"Authorization": f"Bearer {_apimart_key()}",
                     "Content-Type": "application/json",
                     "anthropic-version": "2023-06-01"},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    ev = json.loads(raw)
                except Exception:
                    continue
                if ev.get("type") == "content_block_delta":
                    text = ev.get("delta", {}).get("text", "")
                    if text:
                        yield text
                elif ev.get("type") == "error":
                    raise RuntimeError(f"Apimart Vision 错误: {ev.get('error', ev)}")


async def _stream_openai_vision(
    prompt: str, images_b64: list[str],
    api_key: str, base_url: str = "https://api.openai.com",
    model: str = "gpt-4o",
) -> AsyncGenerator[str, None]:
    """GPT-4o / OpenAI-compatible vision (image_url content blocks)."""
    content: list[dict] = []
    for uri in images_b64[:4]:
        content.append({"type": "image_url", "image_url": {"url": uri, "detail": "high"}})
    content.append({"type": "text", "text": prompt})

    payload = {"model": model, "max_tokens": 8192,
               "messages": [{"role": "user", "content": content}], "stream": True}
    # 与文本链同一约定：assistant_base_url 可能已含 /v1（openrouter 等），别重复拼。
    base = base_url.rstrip("/")
    url = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=30)) as client:
        async with client.stream(
            "POST", url, json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    ev = json.loads(raw)
                except Exception:
                    continue
                text = (ev.get("choices") or [{}])[0].get("delta", {}).get("content", "")
                if text:
                    yield text


async def _stream_ivyea_agent_vision(prompt: str, images_b64: list[str],
                                     observed: dict | None = None) -> AsyncGenerator[str, None]:
    """ivyea-agent 作视觉 provider：serve /v1/chat/stream 带 images（v1.8.3+）。

    persist=False —— 成图复核/图片分析属于内部管线调用，不进 agent 会话历史。
    max_steps=1 —— 看图回答是单步任务，不需要 agent 工具循环。

    `observed` 传进来时，会把 agent 上报的**本次请求实际档位**（vision_tier 事件）
    写进去。用它而不是 /health 快照：旁路在请求中途失败会就地降到 T3，快照还停在
    T2，标签就会虚报成"真看见了"。
    """
    from app.services import ivyea_agent_service as ivyea

    status = await asyncio.to_thread(ivyea.ensure_available)
    if not status.get("available"):
        raise RuntimeError(status.get("error") or "IvyeaAgent 服务未连接")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    token = ivyea._token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {
        "message": prompt,
        "images": [uri for uri in images_b64[:4] if str(uri).startswith("data:image/")],
        "max_steps": 1,
        "plan_mode": True,
        "persist": False,
        "inject_retrieval": False,
    }
    got_token = False
    final_text = ""
    event = "message"
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=15)) as client:
        async with client.stream("POST", f"{ivyea.base_url()}/v1/chat/stream", json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line:
                    event = "message"
                    continue
                if line.startswith("event:"):
                    event = line[6:].strip() or "message"
                    continue
                if not line.startswith("data:"):
                    continue
                try:
                    data = json.loads(line[5:].strip() or "{}")
                except Exception:
                    continue
                if event == "token":
                    text = str(data.get("text") or "")
                    if text:
                        got_token = True
                        yield text
                elif event == "vision_tier":
                    if observed is not None and isinstance(data, dict):
                        observed.update(data)
                elif event == "final":
                    final_text = str(data.get("text") or "")
                    if observed is not None and isinstance(data.get("vision_tier"), dict):
                        observed.update(data["vision_tier"])
                elif event == "error":
                    raise RuntimeError(str(data.get("detail") or data.get("error") or data))
    if not got_token and final_text:
        yield final_text


async def stream_vision(prompt: str, images_b64: list[str]) -> AsyncGenerator[tuple[str, str], None]:
    """Vision fallback chain: tries each configured vision provider in order.

    Each element of images_b64 should be a data-URI string like
    'data:image/jpeg;base64,...' as produced by FileReader.readAsDataURL().
    Yields (provider_name, text_chunk) tuples; on total failure yields ('error', detail).
    """
    chain = _vision_provider_chain()
    if not chain:
        # 走到这里说明连 agent 都不可达（agent 只要在线就至少有 T3 本地 CV）。
        # 所以文案不能再说"没配视觉模型就做不了"——没配视觉模型是能做的，
        # 前提是 agent 服务活着。
        yield "error", (
            "当前没有任何可用的视觉通道。\n"
            "  · 首选：确认 IvyeaAgent 服务在线——它自带三档降级，"
            "即使主脑不支持图片，也会用第三方视觉模型旁路或本地 CV+OCR 量化处理。\n"
            "  · 或在「系统配置 → AI 服务」配置 OpenAI API key（GPT-4o）"
            "或支持视觉的自定义 assistant provider。"
        )
        return

    failures: list[str] = []
    for provider in chain:
        try:
            got = False
            observed: dict = {}      # agent 上报的本次实际档位，其余 provider 留空
            if provider == "ivyea-agent":
                # 标签带上档位：上层（Listing）要按档位决定哪些分析做得了，
                # 前端也要显示"本次是哪一档的结果"。降级本身不是问题，
                # 降级了却不说才是。
                #
                # 先用 /health 快照兜个底，拿到 agent 上报的 vision_tier 事件后
                # 立刻换成**本次实测**的档位——旁路中途失败会就地降到 T3，
                # 只信快照就会把编不出来的那一档报成"真看见了"。
                snapshot = _agent_vision_chain().get("tier")
                label = f"ivyea-agent/t{snapshot}" if isinstance(snapshot, int) and snapshot else "ivyea-agent"
                gen = _stream_ivyea_agent_vision(prompt, images_b64, observed)
            elif provider == "apimart":
                label = "claude"
                gen = _stream_apimart_vision(prompt, images_b64)
            elif provider == "openai":
                label = "gpt-4o"
                gen = _stream_openai_vision(prompt, images_b64, _openai_key())
            else:  # assistant
                cfg = _assistant_vision_cfg()
                if not cfg:
                    continue
                _, key, base, model = cfg
                label = "assistant"
                # Anthropic-format providers go through Apimart-style; others use OpenAI compat.
                if "anthropic" in cfg[0] or "apimart" in cfg[0]:
                    gen = _stream_apimart_vision(prompt, images_b64)
                else:
                    gen = _stream_openai_vision(prompt, images_b64, key,
                                                base or "https://api.openai.com/v1",
                                                model=model or "gpt-4o")

            async for chunk in gen:
                got = True
                # vision_tier 事件在首个 token 之前到达，所以从第一段起标签就是真的。
                live = observed.get("tier")
                yield (f"ivyea-agent/t{live}" if isinstance(live, int) and live else label), chunk
            if got:
                return
            failures.append(f"{provider}: 返回空")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{provider}: {exc}")
            _log.warning("vision provider %s failed: %s", provider, exc)

    yield "error", (
        "所有视觉 AI 提供商均不可用：\n"
        + "\n".join(f"  · {f}" for f in failures)
        + "\n\n已尝试的提供商顺序：" + " → ".join(chain)
    )


async def stream_text(prompt: str) -> AsyncGenerator[tuple[str, str], None]:
    """Streaming counterpart of ``generate_text``: yields (provider, chunk).

    For llm-only skill execution where we want token-by-token UX but NO tools /
    MCP. Uses the configured safe text chain first. On total failure yields
    ('error', detail).
    """
    failures: list[str] = []
    tried: set[str] = set()

    async def _run_provider(provider: str) -> AsyncGenerator[tuple[str, str], None]:
        tried.add(provider)
        if provider == "ivyea-agent":
            gen = _try_ivyea_agent(prompt, failures)
        elif provider == "assistant":
            gen = _try_assistant(prompt, failures)
        elif provider == "deepseek":
            gen = _try_deepseek(prompt, failures)
        elif provider == "apimart":
            gen = _try_apimart(prompt, failures)
        else:
            return
        async for prov, chunk in gen:
            if prov == "_attempt":
                continue
            yield prov, chunk

    for provider in [p for p in _text_provider_chain() if p in ("ivyea-agent", "assistant", "deepseek", "apimart")]:
        if provider in tried:
            continue
        got = False
        async for prov, chunk in _run_provider(provider):
            got = True
            yield prov, chunk
        if got:
            return

    # Legacy fallback: keep Apimart reachable for older configs that still
    # expect it, even though it is no longer part of the default text chain.
    for provider in ("ivyea-agent", "assistant", "deepseek", "apimart"):
        if provider in tried:
            continue
        got = False
        async for prov, chunk in _run_provider(provider):
            got = True
            yield prov, chunk
        if got:
            return

    yield "error", (
        "无可用文本模型。"
        + (" / ".join(failures) if failures else "请在「系统配置」配置 IvyeaAgent / 全局兜底大模型 / DeepSeek。")
    )


async def _stream_openai_compat(
    api_key: str, base_url: str, model: str, prompt: str
) -> AsyncGenerator[str, None]:
    """Stream tokens via any OpenAI-compatible chat/completions endpoint."""
    payload = {
        "model": model,
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=30)) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                except Exception:
                    continue
                choices = event.get("choices", [])
                if not choices:
                    continue
                text = choices[0].get("delta", {}).get("content", "")
                if text:
                    yield text


async def _try_deepseek(prompt: str, failures: list[str]) -> AsyncGenerator[tuple[str, str], None]:
    """Stream market research synthesis via DeepSeek HTTP API (true streaming).

    DeepSeek uses the OpenAI-compatible streaming format, so each token
    arrives as a separate SSE event — no waiting for the full response.
    Falls back gracefully by pushing a diagnostic to ``failures``.
    """
    yield "_attempt", "deepseek"
    key = _deepseek_key()
    if not key:
        failures.append(
            "DeepSeek API key 未配置 — 在「系统配置」中添加 deepseek_api_key，"
            "或在 ~/.hermes/.env 中设置 DEEPSEEK_API_KEY=sk-..."
        )
        return
    try:
        async for chunk in _stream_openai_compat(
            key, "https://api.deepseek.com", "deepseek-chat", prompt
        ):
            yield "deepseek", chunk
        return
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        body = ""
        try:
            body = exc.response.text[:200] if exc.response is not None else ""
        except Exception:
            logger.debug("body = exc.response.text 失败（旁路，已忽略）", exc_info=True)
        failures.append(f"DeepSeek HTTP {code}：{body or '请求失败'}")
        _log.warning("deepseek failed: HTTP %s — %s", code, body)
    except Exception as exc:
        failures.append(f"DeepSeek 调用失败：{exc}")
        _log.warning("deepseek failed: %s", exc)


async def _stream_cli_runner(runner: str, prompt: str) -> AsyncGenerator[str, None]:
    """Stream stdout from a CLI runner as it produces output.

    Raises RuntimeError if the binary is missing, the 300 s deadline is
    exceeded, or the process exits without producing any output.
    """
    binary = _find_bin(runner)
    if not binary:
        raise RuntimeError(f"{runner} CLI 不可用")

    env = build_child_env(binary)
    env.setdefault("TERM", "dumb")
    env.setdefault("FORCE_COLOR", "0")
    env.setdefault("NO_COLOR", "1")
    env.setdefault("HERMES_ACCEPT_HOOKS", "1")

    argv = _build_runner_cmd(runner, binary, prompt)

    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        cwd=str(Path.home()),
        env=env,
        **no_window_kwargs(),
    )

    total_chars = 0
    timed_out = False
    loop = asyncio.get_running_loop()
    timeout_s = 300
    deadline = loop.time() + timeout_s
    # Use asyncio.wait() rather than wait_for() so we never cancel the reader
    # coroutine mid-flight; cancelling StreamReader.read() can corrupt the
    # internal buffer on Python < 3.12.
    read_task: asyncio.Task[bytes] = asyncio.create_task(proc.stdout.read(4096))

    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                timed_out = True
                break
            done, _ = await asyncio.wait([read_task], timeout=min(remaining, 30))
            if not done:
                # 30 s of silence: if the process already exited, the pipe
                # won't produce EOF until the read_task drains — break out.
                if proc.returncode is not None:
                    read_task.cancel()
                    break
                continue  # still running — keep waiting
            chunk = read_task.result()
            if not chunk:  # EOF
                break
            text = _ANSI_RE.sub("", chunk.decode("utf-8", errors="replace"))
            if text:
                total_chars += len(text)
                yield text
            read_task = asyncio.create_task(proc.stdout.read(4096))
    finally:
        if not read_task.done():
            read_task.cancel()
        if proc.returncode is None:
            proc.kill()
            try:
                await asyncio.wait_for(proc.communicate(), timeout=5)
            except Exception:
                logger.debug("asyncio.wait_for 失败（旁路，已忽略）", exc_info=True)

    if timed_out:
        raise RuntimeError(f"{runner} CLI 超时（{timeout_s}s）")
    if total_chars == 0:
        raise RuntimeError(
            f"{runner} CLI 返回空内容"
            + (f"（退出码 {proc.returncode}）" if proc.returncode else "")
        )
    if proc.returncode and proc.returncode != 0:
        _log.warning("%s exited %s after streaming %d chars", runner, proc.returncode, total_chars)


async def _try_apimart(prompt: str, failures: list[str]) -> AsyncGenerator[tuple[str, str], None]:
    """Yield (provider, chunk) tuples from Apimart streaming; on failure
    push a human-readable reason into ``failures`` and return.

    Emits a sentinel ('_attempt', 'apimart') *before* the real network call
    so the UI can show 'trying apimart…' without waiting for a token.
    """
    yield "_attempt", "apimart"
    if not _apimart_key():
        failures.append("Apimart 密钥未配置（系统配置 → AI 服务）")
        return
    try:
        async for chunk in _stream_apimart(prompt):
            yield "claude", chunk
        return
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        body_preview = ""
        try:
            body_preview = exc.response.text[:200] if exc.response is not None else ""
        except Exception:
            logger.debug("body_preview = exc.response.text 失败（旁路，已忽略）", exc_info=True)
        if code in (401, 403):
            failures.append(
                f"Apimart 密钥被拒（HTTP {code}）— 该密钥可能仅有图片权限，没买 Claude 文本。"
                " 在「系统配置 → 文本 AI 提供商」把 apimart 从列表中删掉即可避免重试。"
                + (f"  返回: {body_preview}" if body_preview else "")
            )
        elif code == 429:
            failures.append("Apimart 限流（HTTP 429）— 稍后重试或升级套餐。")
        else:
            failures.append(f"Apimart HTTP {code}：{body_preview or '请求失败'}")
        _log.warning("apimart failed: HTTP %s — %s", code, body_preview)
    except Exception as exc:
        failures.append(f"Apimart 调用失败：{exc}")
        _log.warning("apimart failed: %s", exc)


async def _try_cli(runner: str, prompt: str, failures: list[str]) -> AsyncGenerator[tuple[str, str], None]:
    """Yield ('_attempt', runner) sentinel then stream chunks from the CLI."""
    yield "_attempt", runner
    if not _find_bin(runner):
        failures.append(f"{runner} CLI 未安装（PATH 找不到 / 未在「系统配置 → 外部集成路径」配置）")
        return
    try:
        async for chunk in _stream_cli_runner(runner, prompt):
            yield runner, chunk
    except Exception as exc:
        failures.append(f"{runner} CLI 失败：{exc}")
        _log.warning("%s failed: %s", runner, exc)






async def run_text_chain(
    prompt: str, *, order: list[str] | None = None, agent_retrieval: bool = True
) -> tuple[str, str]:
    """Canonical text generation over the standard fallback chain.

    The single entry point every board should use for "write me text" tasks:
    IvyeaAgent → DeepSeek → global fallback model → Codex → Claude
    (or a custom ``order``).
    Returns ``(provider, text)`` for the first provider that yields output.
    Raises ``RuntimeError`` with a diagnostic if the whole chain fails.

    Use ``stream_text`` for token-by-token streaming.
    """
    chain = order or _text_provider_chain()
    failures: list[str] = []
    for provider in chain:
        if provider == "ivyea-agent":
            gen = _try_ivyea_agent(prompt, failures, inject_retrieval=agent_retrieval)
        elif provider == "deepseek":
            gen = _try_deepseek(prompt, failures)
        elif provider == "apimart":
            gen = _try_apimart(prompt, failures)
        elif provider == "assistant":
            gen = _try_assistant(prompt, failures)
        else:
            gen = _try_cli(provider, prompt, failures)
        parts: list[str] = []
        async for prov, chunk in gen:
            if prov != "_attempt":
                parts.append(chunk)
        text = "".join(parts).strip()
        if text:
            # Observability: record which provider in the chain actually answered
            # (and how many earlier ones were skipped/failed) for ops debugging.
            if failures:
                _log.info(
                    "run_text_chain: '%s' answered after %d failure(s): %s",
                    provider, len(failures), " | ".join(failures)[:300],
                )
            else:
                _log.info("run_text_chain: '%s' answered (%d chars)", provider, len(text))
            record_ai_call(provider, True, chars=len(text), failures=failures)
            return provider, text
    record_ai_call("(none)", False, failures=failures)
    raise RuntimeError(
        "所有文本 AI 提供商均不可用：\n"
        + "\n".join(f"  • {f}" for f in failures)
        + f"\n\n当前提供商顺序：{', '.join(chain) or '（空）'}"
    )
