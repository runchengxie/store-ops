"""Exercise registered APIs through the actual application, including SPA routing."""
from fastapi.testclient import TestClient


def test_private_insights_routes_are_not_swallowed_by_spa():
    from app.main import app
    client = TestClient(app)
    for method, path in (
        ('GET', '/api/emag/knowledge/status'),
        ('GET', '/api/emag/knowledge/search?q=variant'),
        ('GET', '/api/emag/knowledge/sources/synthetic'),
        ('GET', '/api/emag/stores/synthetic/decision-support'),
        ('POST', '/api/emag/stores/synthetic/preflight'),
        ('POST', '/api/emag/stores/synthetic/promotion-check/1'),
    ):
        assert client.request(method, path).status_code in (401, 403), path
