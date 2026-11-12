import pytest

from app.services.search_service import build_search_query


def test_build_search_query_with_filters():
    query = build_search_query(
        q="login",
        level="warning",
        service="auth-service",
        date_from="2026-01-01T00:00:00Z",
        date_to="2026-01-02T00:00:00Z",
    )
    assert query["bool"]["must"]
    assert len(query["bool"]["filter"]) == 3


def test_build_search_query_rejects_invalid_level():
    with pytest.raises(ValueError):
        build_search_query(level="NOT_A_LEVEL")


def test_search_and_stats(client, admin_headers):
    response = client.get("/api/v1/logs?q=login", headers=admin_headers)
    assert response.status_code == 200
    assert response.get_json()["total"] == 0

    response = client.get("/api/v1/stats", headers=admin_headers)
    assert response.status_code == 200
    assert "total_logs" in response.get_json()["stats"]
