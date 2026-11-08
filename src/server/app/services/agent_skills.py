"""Application eMAG skill mount; user-owned libraries remain untouched."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from app.core.skill_paths import SKILLS_ROOT

logger = logging.getLogger("ivyea.services.agent_skills")

#: Only the shipped eMAG domain is exposed to the shared Agent runtime.
EXPOSED_DOMAINS: tuple[str, ...] = ("emag",)


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
    exists = path.exists()
    try:
        settings = json.loads(path.read_text(encoding="utf-8")) if exists else {}
    except (ValueError, OSError):
        return {"changed": False, "roots": [], "error": "Cannot read agent settings; preserved"}
    if not isinstance(settings, dict):
        return {"changed": False, "roots": []}
    current = settings.get("skill_roots", [])
    retired = str(Path(SKILLS_ROOT) / "amazon")
    if isinstance(current, str):
        values = [current] if current else []
    elif isinstance(current, list):
        values = list(current)
    else:
        return {"changed": False, "roots": []}
    merged = [root for root in values if root != retired]
    for root in exposed_roots():
        if root.is_dir() and str(root) not in merged:
            merged.append(str(root))
    if merged == values and (exists or not merged):
        return {"changed": False, "roots": merged}
    settings["skill_roots"] = merged
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(settings, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
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
