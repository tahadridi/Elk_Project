from tests.conftest import login


def test_admin_creates_user(client, admin_headers):
    response = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "username": "newuser",
            "password": "NewUserPass123!",
            "role": "user",
        },
    )
    assert response.status_code == 201
    assert response.get_json()["user"]["username"] == "newuser"

    response = login(client, "newuser", "NewUserPass123!")
    assert response.status_code == 200


def test_non_admin_cannot_create_user(client, user_headers):
    response = client.post(
        "/api/v1/admin/users",
        headers=user_headers,
        json={
            "username": "forbidden",
            "password": "ForbiddenPass123!",
            "role": "admin",
        },
    )
    assert response.status_code == 403


def test_admin_updates_geo_settings(client, admin_headers):
    response = client.put(
        "/api/v1/admin/settings/geo",
        headers=admin_headers,
        json={
            "enabled": True,
            "mode": "allowlist",
            "allowed_countries": ["TN", "FR"],
            "blocked_countries": [],
            "unknown_country": "deny",
            "allow_private_ips": True,
        },
    )
    assert response.status_code == 200
    settings = response.get_json()["settings"]
    assert settings["mode"] == "allowlist"
    assert "TN" in settings["allowed_countries"]


def test_admin_geo_settings_reject_empty_allowlist(client, admin_headers):
    response = client.put(
        "/api/v1/admin/settings/geo",
        headers=admin_headers,
        json={
            "enabled": True,
            "mode": "allowlist",
            "allowed_countries": [],
            "blocked_countries": [],
            "unknown_country": "deny",
            "allow_private_ips": True,
        },
    )
    assert response.status_code == 400


def test_admin_can_list_security_events(client, admin_headers):
    response = client.get("/api/v1/admin/security-events", headers=admin_headers)
    assert response.status_code == 200
    assert "items" in response.get_json()
