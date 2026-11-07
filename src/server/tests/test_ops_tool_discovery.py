"""Tool discovery preserves shared search and permission boundaries."""
from app.services.ivyea_ops_tools import list_tools

ADMIN = {"role": "admin", "email": "admin", "permissions": []}


def test_multi_word_query_matches_any_word():
    rows = list_tools(query="missingword image", principal=ADMIN)["tools"]
    assert {"image_generate", "image_status", "show_image"} <= {row["name"] for row in rows}


def test_module_filters_shared_tools():
    rows = list_tools(module="servmon", principal=ADMIN)["tools"]
    assert {row["name"] for row in rows} == {"monitor_snapshot", "monitor_services", "monitor_token_usage"}


def test_ungranted_user_cannot_discover_privileged_tools():
    user = {"role": "user", "permissions": []}
    assert list_tools(module="servmon", principal=user)["tools"] == []
