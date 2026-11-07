"""Application skill mount retirement; user-owned libraries remain untouched."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from app.core.skill_paths import SKILLS_ROOT

logger = logging.getLogger("ivyea.services.agent_skills")

#: No application-managed external skill domains are currently exposed.
EXPOSED_DOMAINS: tuple[str, ...] = ()


def _agent_settings_file() -> Path:
    """agent 的 settings.json —— 和它自己一样认 IVYEA_HOME。"""
    home = os.environ.get("IVYEA_HOME") or str(Path.home() / ".ivyea")
    return Path(home) / "settings.json"


def exposed_roots() -> list[Path]:
    return [Path(SKILLS_ROOT) / d for d in EXPOSED_DOMAINS]


def register_roots() -> dict[str, Any]:
    """把技能库根目录写进 agent 的 settings.json。幂等。

    **合并而不是覆盖** `skill_roots`：用户可能自己挂了别的库，我们只负责自己这几条。
    """
    path = _agent_settings_file()
    if not path.exists():
        return {"changed": False, "roots": []}
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"changed": False, "roots": [], "error": "Cannot read agent settings; preserved"}
    if not isinstance(settings, dict):
        return {"changed": False, "roots": []}
    current = settings.get("skill_roots", [])
    # Only the precise historical mount owned by this application is retired.
    # Do not normalize, classify or delete arbitrary user paths or skill files.
    retired = str(Path(SKILLS_ROOT) / "amazon")
    if isinstance(current, str):
        merged = [] if current == retired else current
    elif isinstance(current, list):
        merged = [root for root in current if root != retired]
    else:
        return {"changed": False, "roots": []}
    if merged == current:
        return {"changed": False, "roots": merged}
    settings["skill_roots"] = merged
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"changed": True, "roots": merged}


def register_quietly() -> None:
    try:
        register_roots()
    except Exception:
        logger.warning("挂载技能库失败（旁路，已忽略）", exc_info=True)


def skill_dir(name: str) -> str:
    """一个 Skill 中心技能在磁盘上的绝对路径。

    执行技能时把它告诉模型，说明书里的 `scripts/` `references/` 才拿得到 ——
    以前这里只能反过来叮嘱它"不要去文件系统里找"。
    """
    try:
        d = (Path(SKILLS_ROOT) / name).resolve()
        root = Path(SKILLS_ROOT).resolve()
        if d.is_dir() and (d == root or root in d.parents):
            return str(d)
    except Exception:
        logger.debug("skill_dir 解析失败（旁路）", exc_info=True)
    return ""


def status() -> dict[str, Any]:
    """挂了哪些目录、agent 那边实际认出多少个技能 —— 给 Skill 中心显示。"""
    roots = exposed_roots()
    registered: list[str] = []
    try:
        settings = json.loads(_agent_settings_file().read_text(encoding="utf-8"))
        registered = [str(x) for x in (settings.get("skill_roots") or [])]
    except Exception:
        logger.debug("读 agent settings.json 失败（旁路）", exc_info=True)

    # 数一下这些目录里到底有多少个技能。**按 agent 的判据数**（有 SKILL.md 就算），
    # 别自己另算一套，否则界面显示的数和 agent 真认的数会对不上。
    count = 0
    for r in roots:
        if r.is_dir():
            count += sum(1 for p in r.rglob("SKILL.md")
                         if not any(seg.startswith(".") for seg in p.relative_to(r).parts))
    return {
        "domains": list(EXPOSED_DOMAINS),
        "roots": [str(r) for r in roots],
        "registered": all(str(r) in registered for r in roots if r.is_dir()),
        "count": count,
    }
