"""把 Skill 中心的技能库挂给 IvyeaAgent。

这层现在只做一件事：往 agent 的 settings.json 里写一个目录。**不复制、不转格式** ——
agent 从 v1.14 起直接认 SKILL.md + frontmatter。
"""
from __future__ import annotations

import pytest

from app.services import agent_skills


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """技能库和 agent home 都指到临时目录，绝不碰真实的 ~/.ivyea。"""
    hub = tmp_path / "skills"
    (hub / "amazon" / "demo").mkdir(parents=True)
    (hub / "amazon" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n正文", encoding="utf-8")
    monkeypatch.setattr(agent_skills, "SKILLS_ROOT", hub)
    monkeypatch.setenv("IVYEA_HOME", str(tmp_path / "agent-home"))
    return hub, tmp_path / "agent-home"


def test_no_application_skill_roots_are_exposed(_isolated):
    _, home = _isolated
    assert agent_skills.register_roots()["changed"] is False
    assert not (home / "settings.json").exists()
    assert agent_skills.status() == {"domains": [], "roots": [], "registered": True, "count": 0}


def test_skill_dir_returns_the_real_path(_isolated):
    hub, _ = _isolated
    assert agent_skills.skill_dir("amazon/demo") == str((hub / "amazon" / "demo").resolve())


def test_skill_dir_refuses_to_escape_the_library(_isolated):
    """名字来自请求参数，不能拿它遍历文件系统。"""
    assert agent_skills.skill_dir("../../etc") == ""
    assert agent_skills.skill_dir("amazon/nope") == ""
