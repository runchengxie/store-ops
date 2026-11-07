"""Executable catalogs must expose only current platform and shared capabilities."""
import ast
import asyncio
from pathlib import Path

from app.services import ivyea_ops_tools

RETIRED = ('amazon', 'ad-audit', 'cockpit', 'lingxing', 'market', 'home', 'playbook', 'news', 'deep-analysis', 'listing', 'data-sources')


def test_retired_routes_are_absent():
    from app.main import app
    paths = set(app.openapi()['paths'])
    for prefix in RETIRED:
        assert not any(path == f'/api/{prefix}' or path.startswith(f'/api/{prefix}/') for path in paths), prefix
    assert '/api/emag/stores' in paths


def test_bridge_catalog_cannot_dispatch_retired_tools():
    names = {tool.name for tool in ivyea_ops_tools.TOOLS}
    assert names == {'image_generate', 'image_status', 'show_image', 'monitor_snapshot', 'monitor_services', 'monitor_token_usage', 'skill_tools_list'}
    for name in ('asin_audit_start', 'lingxing_operate', 'market_generate_report', 'listing_scrape'):
        assert asyncio.run(ivyea_ops_tools.call_tool(name))['error'] == 'tool_not_found'


def test_startup_has_no_retired_provider_imports():
    tree = ast.parse((Path(__file__).parents[1] / 'app/main.py').read_text())
    imports = {node.module or '' for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(module.rsplit('.', 1)[-1] in {'asin_audit', 'ad_audit', 'market', 'home', 'playbook', 'lingxing_service', 'lingxing_automation', 'cockpit_sync'} for module in imports)


def test_public_mcp_rejects_retired_tools():
    from app.routers import mcp_server
    for name in ('ivyea_ads_findings', 'ivyea_keyword_research', 'ivyea_knowledge_search'):
        assert name not in mcp_server.TOOLS
        assert asyncio.run(mcp_server._call_tool(name, {}))['isError'] is True


def test_shared_runner_auto_ignores_retired_audit_preferences(monkeypatch):
    from app.services import runners
    from app.core import hub_settings
    monkeypatch.setattr(hub_settings, 'get', lambda *args: 'hermes')
    monkeypatch.setattr(runners, '_find_bin', lambda name: f'/bin/{name}')
    assert runners._resolve_auto() == ('ivyea-agent', '/bin/ivyea-agent')
