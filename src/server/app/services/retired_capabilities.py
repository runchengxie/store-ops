"""Finite migration identifiers for capabilities removed from this application.

This catalog is a dispatch guard, never an implementation or a free-text
marketplace classifier. External agent installations/configuration remain private.
"""
from __future__ import annotations

import re

RETIRED_SKILLS = frozenset(['amazon-ad-campaign-optimization-xlsx', 'amazon-asin-cosmo-rufus-audit', 'amazon-listing-creative', 'zach-search-term-report-analyzer'])
RETIRED_TOOLS = frozenset(['ad_audit_list', 'ad_audit_start', 'ad_audit_status', 'asin_audit_list', 'asin_audit_start', 'asin_audit_status', 'deep_analysis_history', 'deep_competitor_lookup', 'deep_generate_report', 'deep_keyword_competition', 'deep_traffic_diagnosis', 'home_add_watch', 'home_list_watch', 'home_pulse', 'ivyea_ads_findings', 'ivyea_keyword_research', 'ivyea_knowledge_search', 'ivyea_ops_ad_audit_list', 'ivyea_ops_ad_audit_start', 'ivyea_ops_ad_audit_status', 'ivyea_ops_asin_audit_list', 'ivyea_ops_asin_audit_start', 'ivyea_ops_asin_audit_status', 'ivyea_ops_audit_asin', 'ivyea_ops_deep_analysis_history', 'ivyea_ops_deep_competitor_lookup', 'ivyea_ops_deep_generate_report', 'ivyea_ops_deep_keyword_competition', 'ivyea_ops_deep_traffic_diagnosis', 'ivyea_ops_home_add_watch', 'ivyea_ops_home_list_watch', 'ivyea_ops_home_pulse', 'ivyea_ops_lingxing_dashboard', 'ivyea_ops_lingxing_datasets', 'ivyea_ops_lingxing_operate', 'ivyea_ops_lingxing_operate_disable', 'ivyea_ops_lingxing_operate_enable', 'ivyea_ops_lingxing_operate_tickets', 'ivyea_ops_lingxing_optimizer', 'ivyea_ops_lingxing_read', 'ivyea_ops_lingxing_status', 'ivyea_ops_listing_copy_jobs', 'ivyea_ops_listing_create_copy_job', 'ivyea_ops_listing_create_project', 'ivyea_ops_listing_get_copy_job', 'ivyea_ops_listing_get_project', 'ivyea_ops_listing_projects', 'ivyea_ops_listing_scrape', 'ivyea_ops_listing_start_copy_job', 'ivyea_ops_market_collect_data', 'ivyea_ops_market_generate_report', 'ivyea_ops_market_history', 'ivyea_ops_news_latest', 'ivyea_ops_news_refresh', 'ivyea_ops_playbook_generate_report', 'ivyea_ops_playbook_history', 'lingxing_dashboard', 'lingxing_datasets', 'lingxing_operate', 'lingxing_operate_disable', 'lingxing_operate_enable', 'lingxing_operate_tickets', 'lingxing_optimizer', 'lingxing_read', 'lingxing_status', 'listing_copy_jobs', 'listing_create_copy_job', 'listing_create_project', 'listing_get_copy_job', 'listing_get_project', 'listing_projects', 'listing_scrape', 'listing_start_copy_job', 'market_collect_data', 'market_generate_report', 'market_history', 'mcp_sellersprite_asin_keywords', 'mcp_sellersprite_competitor_keywords', 'mcp_sellersprite_keyword_research', 'mcp_sellersprite_keyword_traffic', 'mcp_sif_competitor_keyword_signals', 'mcp_sif_keyword_competition', 'mcp_sif_traffic_anomaly', 'mcp_sorftime_category_report', 'mcp_sorftime_category_search_from_product_name', 'mcp_sorftime_competitor_product_keywords', 'mcp_sorftime_keyword_detail', 'mcp_sorftime_keyword_extends', 'mcp_sorftime_keyword_search_results', 'mcp_sorftime_keyword_trend', 'mcp_sorftime_potential_product', 'mcp_sorftime_product_detail', 'mcp_sorftime_product_reviews', 'mcp_sorftime_product_traffic_terms', 'mcp_sorftime_product_trend', 'mcp_sorftime_product_variations', 'mcp_sorftime_similar_product_feature', 'news_latest', 'news_refresh', 'playbook_generate_report', 'playbook_history'])
# Match complete capability identifier tokens, never product/provider keywords.
_REFERENCE = re.compile(r"[A-Za-z0-9_./-]+")


def retired_reference(*, skill: str = "", prompt: str = "") -> str:
    """Return the exact retired identifier, or empty for ordinary free text."""
    references = [skill.strip()] if skill.strip() else []
    references.extend(_REFERENCE.findall(prompt))
    for reference in references:
        if reference in RETIRED_TOOLS or reference.rsplit("/", 1)[-1] in RETIRED_SKILLS:
            return reference
    return ""
