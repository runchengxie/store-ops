"""Shared text provider fallback contract."""
from app.services import ai_synthesis_service


def test_default_text_chain_leads_with_ivyea_agent():
    assert ai_synthesis_service._text_provider_chain()[0] == "ivyea-agent"
