"""Retired provider settings cannot provision an external agent registry."""
from app.services import hermes_config_sync as sync


def test_old_keys_do_not_create_agent_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("IVYEA_HOME", str(tmp_path))
    sync.on_settings_saved({"sorftime_key": "key", "sif_key": "key", "sellersprite_key": "key"})
    assert not (tmp_path / "mcp.json").exists()


def test_existing_registry_is_byte_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("IVYEA_HOME", str(tmp_path))
    path = tmp_path / "mcp.json"
    original = '{"mcpServers":{"sif_mcp":{"url":"private"},"mine":{"env":{"SECRET":"keep"}}}}'
    path.write_text(original)
    sync.on_settings_saved({"sorftime_key": "key", "sif_key": "", "sellersprite_key": "key"})
    assert path.read_text() == original
