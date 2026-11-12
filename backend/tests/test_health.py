def test_health_reports_dependencies(client):
    response = client.get("/health")
    assert response.status_code in {200, 503}
    payload = response.get_json()
    assert payload["status"] in {"healthy", "degraded", "down"}
    assert "mongodb" in payload["checks"]
    assert "redis" in payload["checks"]
    assert "elasticsearch" in payload["checks"]
