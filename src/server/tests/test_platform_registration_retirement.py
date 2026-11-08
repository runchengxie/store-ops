"""Retired application capabilities cannot be re-provisioned or dispatched."""
import json
import pytest
from app.services import agent_skills, hermes_config_sync, agent_mcp, schedules
from app.core import hub_settings


def test_upgrade_removes_only_owned_skill_mount(tmp_path, monkeypatch):
    root = tmp_path / "skills"
    (root / "amazon").mkdir(parents=True)
    path = tmp_path / "settings.json"
    original = {"skill_roots": ["/user/amazon", str(root / "amazon"), "/user/emag"], "private": {"token": "secret"}}
    path.write_text(json.dumps(original))
    monkeypatch.setattr(agent_skills, "SKILLS_ROOT", root)
    monkeypatch.setattr(agent_skills, "_agent_settings_file", lambda: path)
    agent_skills.register_roots()
    assert json.loads(path.read_text()) == {**original, "skill_roots": ["/user/amazon", "/user/emag"]}
    assert agent_skills.exposed_roots() == [root / "emag"]
    assert agent_skills.register_roots()["changed"] is False


@pytest.mark.parametrize("content", [None, "{broken", '{"skill_roots": ["/private"]}'])
def test_no_registration_preserves_absent_or_private_config(tmp_path, monkeypatch, content):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(agent_skills, "SKILLS_ROOT", tmp_path / "absent-skills")
    if content is not None:
        path.write_text(content)
    monkeypatch.setattr(agent_skills, "_agent_settings_file", lambda: path)
    agent_skills.register_roots()
    assert (path.read_text() if path.exists() else None) == content


def test_provider_settings_never_touch_external_registry(tmp_path, monkeypatch):
    cfg, mcp = tmp_path / "config.yaml", tmp_path / "mcp.json"
    cfg.write_text("# private\nmcp_servers:\n  sorftime: {url: private}\n")
    mcp.write_text('{"mcpServers":{"sellersprite":{"command":"private"}}}')
    before = cfg.read_bytes(), mcp.read_bytes()
    monkeypatch.setattr(hermes_config_sync, "_HERMES_CFG", cfg)
    monkeypatch.setattr(hermes_config_sync, "_agent_mcp_file", lambda: mcp)
    hermes_config_sync.on_settings_saved({"sorftime_key": "new", "sif_key": "new", "sellersprite_key": "new"})
    assert (cfg.read_bytes(), mcp.read_bytes()) == before
    assert agent_mcp.MANAGED_SERVERS == set()


def test_save_preserves_retired_and_unknown_private_settings(tmp_path, monkeypatch):
    path = tmp_path / "hub_settings.json"
    path.write_text(json.dumps({"sorftime_key": "private", "unknown_private": "retain"}))
    monkeypatch.setattr(hub_settings, "_path", lambda: path)
    from app.core import audit, secrets
    monkeypatch.setattr(audit, "record", lambda *a, **k: None)
    monkeypatch.setattr(secrets, "encrypt_mapping", lambda value: value)
    response = hub_settings.save({"setup_done": True})
    assert "unknown_private" not in response
    assert "sorftime_key" not in response
    assert json.loads(path.read_text())["unknown_private"] == "retain"
    assert json.loads(path.read_text())["sorftime_key"] == "private"
    assert not {"sorftime_key", "sif_key", "sellersprite_key", "audit_default_runner"} & hub_settings._DEFAULTS.keys()


@pytest.mark.parametrize("skill,prompt", [
    ("amazon/amazon-listing-creative", "generate"),
    ("amazon-asin-cosmo-rufus-audit", "audit"),
    ("", "tool:mcp_sorftime_keyword_detail"),
    ("", "tool:ivyea_ops_audit_asin"),
])
def test_schedule_records_retirement_before_agent_dispatch(tmp_path, monkeypatch, skill, prompt):
    monkeypatch.setattr(schedules, "_db_path", lambda: tmp_path / "schedules.sqlite3")
    schedules.init_db()
    from app.services import ivyea_agent_service
    def forbidden(*args, **kwargs):
        pytest.fail("Retired capability reached agent dispatch")
    monkeypatch.setattr(ivyea_agent_service, "ensure_available", forbidden)
    task = schedules.create_task(name="retained", cron="0 9 * * *", prompt=prompt, skill=skill, principal="owner", role="user")
    run = schedules.run_task_now(task)
    assert run["status"] == "error"
    assert "capability_retired" in run["error"]
    assert schedules.get_task(task["id"])["prompt"] == prompt
    assert schedules.get_task(task["id"])["skill"] == skill


def test_arbitrary_prompt_is_not_keyword_classified(tmp_path, monkeypatch):
    monkeypatch.setattr(schedules, "_db_path", lambda: tmp_path / "schedules.sqlite3")
    schedules.init_db()
    from app.services import ivyea_agent_service
    monkeypatch.setattr(ivyea_agent_service, "ensure_available", lambda: {"available": True})
    monkeypatch.setattr(ivyea_agent_service, "chat", lambda payload: {"ok": True, "text": payload["message"]})
    task = schedules.create_task(name="notes", cron="0 9 * * *", prompt="Discuss Amazon rainforest and Sorftime retirement notes", principal="owner", role="user")
    assert schedules.run_task_now(task)["status"] == "done"

@pytest.mark.parametrize("reference", ["Use asin_audit_start for yesterday", "Run mcp_sellersprite_keyword_traffic", "Use ivyea_ads_findings", "Use mcp_sorftime_product_detail"])
def test_explicit_identifier_tokens_are_retired(reference):
    from app.services.retired_capabilities import retired_reference
    assert retired_reference(prompt=reference)


def test_unrelated_similar_identifier_is_not_retired():
    from app.services.retired_capabilities import retired_reference
    assert not retired_reference(prompt="tool:my_asin_audit_start_backup")


def test_retired_skill_is_not_advertised_as_executable(monkeypatch):
    from types import SimpleNamespace
    from app.routers import skill_tools
    retired = SimpleNamespace(name="amazon/amazon-listing-creative", pinned=True, category="amazon", description="", description_zh="")
    monkeypatch.setattr(skill_tools.skill_repo, "list_skills", lambda: [retired])
    assert skill_tools.list_tools().tools == []
    assert skill_tools.list_pinned_tools() == []



def test_knowledge_defaults_are_platform_neutral():
    from app.services import brain_chat_service as brain
    from app.routers.brain import ChatSessionCreateBody
    from pydantic import ValidationError
    assert brain._fallback_ingest_analysis("Amazon ASIN ACOS supplier 1688") ["directory"] == "inbox"
    assert "Amazon" not in brain._build_prompt("Question", [], "knowledge")[0]["content"]
    with pytest.raises(ValidationError):
        ChatSessionCreateBody(mode="amazon_operator")


def test_upgrade_does_not_seed_retired_bundle_or_delete_existing_skill(tmp_path, monkeypatch):
    from app.core import skill_paths
    bundled, library = tmp_path / "bundled", tmp_path / "library"
    retired = "amazon/amazon-listing-creative"
    for name in (retired, "emag/review"):
        path = bundled / name
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text("bundled")
    kept = library / retired / "private.txt"
    kept.parent.mkdir(parents=True)
    kept.write_text("private user extension")
    monkeypatch.setattr(skill_paths, "BUNDLED_SKILLS", bundled)
    monkeypatch.setattr(skill_paths, "SKILLS_ROOT", library)
    assert skill_paths.seed_bundled_skills() == 1
    assert kept.read_text() == "private user extension"
    assert not (kept.parent / "SKILL.md").exists()
    # Fresh installations cannot seed a retired bundled skill either.
    monkeypatch.setattr(skill_paths, "SKILLS_ROOT", tmp_path / "fresh")
    assert skill_paths.seed_bundled_skills() == 1


@pytest.mark.parametrize('skill,prompt', [('', 'Run asin_audit_start.'), ('', 'Run ivyea_ops_asin_audit_start.'), ('amazon/amazon-listing-creative/SKILL.md', 'run'), ('','functions.ivyea_ops_lingxing_status()')])
def test_punctuated_and_file_skill_refs_do_not_dispatch(tmp_path,monkeypatch,skill,prompt):
    monkeypatch.setattr(schedules,'_db_path',lambda:tmp_path/'jobs.sqlite3');schedules.init_db()
    from app.services import ivyea_agent_service
    monkeypatch.setattr(ivyea_agent_service,'ensure_available',lambda:pytest.fail('Retired reference reached Agent'))
    task=schedules.create_task(name='old',cron='0 9 * * *',prompt=prompt,skill=skill,principal='owner',role='user')
    assert 'capability_retired' in schedules.run_task_now(task)['error']


def test_only_emag_mount_is_added_for_fresh_and_upgrade(tmp_path,monkeypatch):
    root=tmp_path/'skills';(root/'emag').mkdir(parents=True)
    path=tmp_path/'agent/settings.json'
    monkeypatch.setattr(agent_skills,'SKILLS_ROOT',root);monkeypatch.setattr(agent_skills,'_agent_settings_file',lambda:path)
    agent_skills.register_roots()
    assert json.loads(path.read_text())['skill_roots']==[str(root/'emag')]
    path.write_text(json.dumps({'skill_roots':['custom',str(root/'amazon')],'private':'retained'}))
    agent_skills.register_roots()
    assert json.loads(path.read_text())=={'skill_roots':['custom',str(root/'emag')],'private':'retained'}
    assert not agent_skills.register_roots()['changed']
