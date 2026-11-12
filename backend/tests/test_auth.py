from app.extensions import get_redis
from app.services.redis_client import failure_count
from tests.conftest import FakeGeoIP, login


def test_login_success(client):
    response = login(client, "admin", "AdminPass123!")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["access_token"]
    assert payload["user"]["role"] == "admin"


def test_login_rejects_wrong_password(client):
    response = login(client, "admin", "wrong-password")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_five_failures_block_ip(client, app):
    for attempt in range(1, 5):
        response = login(client, "user", "wrong-password")
        assert response.status_code == 401
        assert response.get_json()["error"]["details"]["remaining_attempts"] == 5 - attempt

    response = login(client, "user", "wrong-password")
    assert response.status_code == 429
    assert response.get_json()["error"]["code"] == "IP_BLOCKED"

    response = login(client, "user", "UserPass123!")
    assert response.status_code == 429

    with app.app_context():
        assert failure_count("127.0.0.1") >= 5


def test_successful_login_resets_failure_counter(client, app):
    for _ in range(3):
        assert login(client, "admin", "wrong-password").status_code == 401

    with app.app_context():
        assert failure_count("127.0.0.1") == 3

    assert login(client, "admin", "AdminPass123!").status_code == 200

    with app.app_context():
        assert failure_count("127.0.0.1") == 0


def test_role_protection(client, user_headers, admin_headers):
    assert client.get("/api/v1/admin/users", headers=user_headers).status_code == 403
    assert client.get("/api/v1/admin/users", headers=admin_headers).status_code == 200


def test_country_allowlist_denies_unknown_country(client, app, admin_headers):
    with app.app_context():
        from app.services.policy_service import update_section

        update_section(
            "geo",
            {
                "enabled": True,
                "mode": "allowlist",
                "allowed_countries": ["TN"],
                "blocked_countries": [],
                "unknown_country": "deny",
                "allow_private_ips": True,
            },
            updated_by="admin",
        )
        app.extensions["geoip"] = FakeGeoIP(country="US")

    response = login(client, "admin", "AdminPass123!")
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "COUNTRY_BLOCKED"


def test_country_allowlist_allows_listed_country(client, app):
    with app.app_context():
        from app.services.policy_service import update_section

        update_section(
            "geo",
            {
                "enabled": True,
                "mode": "allowlist",
                "allowed_countries": ["TN"],
                "blocked_countries": [],
                "unknown_country": "deny",
                "allow_private_ips": True,
            },
            updated_by="admin",
        )
        app.extensions["geoip"] = FakeGeoIP(country="TN")

    response = login(client, "admin", "AdminPass123!")
    assert response.status_code == 200


def test_unknown_country_is_denied(client, app):
    with app.app_context():
        from app.services.policy_service import update_section

        update_section(
            "geo",
            {
                "enabled": True,
                "mode": "allowlist",
                "allowed_countries": ["TN"],
                "blocked_countries": [],
                "unknown_country": "deny",
                "allow_private_ips": True,
            },
            updated_by="admin",
        )
        app.extensions["geoip"] = FakeGeoIP(country=None)

    response = login(client, "admin", "AdminPass123!")
    assert response.status_code == 403


def test_private_ip_can_be_allowed(client, app):
    with app.app_context():
        from app.services.policy_service import update_section

        update_section(
            "geo",
            {
                "enabled": True,
                "mode": "allowlist",
                "allowed_countries": ["TN"],
                "blocked_countries": [],
                "unknown_country": "deny",
                "allow_private_ips": True,
            },
            updated_by="admin",
        )
        app.extensions["geoip"] = FakeGeoIP(country=None, is_private=True)

    response = login(client, "admin", "AdminPass123!")
    assert response.status_code == 200


def test_address_not_found_is_treated_as_unknown_country(client, app):
    with app.app_context():
        from app.services.policy_service import update_section

        update_section(
            "geo",
            {
                "enabled": True,
                "mode": "allowlist",
                "allowed_countries": ["TN"],
                "blocked_countries": [],
                "unknown_country": "deny",
                "allow_private_ips": True,
            },
            updated_by="admin",
        )
        app.extensions["geoip"] = FakeGeoIP(
            country=None,
            error="address_not_found",
        )

    response = login(client, "admin", "AdminPass123!")
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "COUNTRY_BLOCKED"


def test_geoip_unavailable_fails_open_by_default(client, app):
    with app.app_context():
        from app.services.policy_service import update_section

        update_section(
            "geo",
            {
                "enabled": True,
                "mode": "allowlist",
                "allowed_countries": ["TN"],
                "blocked_countries": [],
                "unknown_country": "deny",
                "allow_private_ips": True,
            },
            updated_by="admin",
        )
        app.extensions["geoip"] = FakeGeoIP(
            country=None,
            error="geoip_unavailable",
        )

    response = login(client, "admin", "AdminPass123!")
    assert response.status_code == 200


def test_geoip_unavailable_fails_closed_when_configured(client, app):
    with app.app_context():
        from app.services.policy_service import update_section

        update_section(
            "geo",
            {
                "enabled": True,
                "mode": "allowlist",
                "allowed_countries": ["TN"],
                "blocked_countries": [],
                "unknown_country": "deny",
                "allow_private_ips": True,
            },
            updated_by="admin",
        )
        app.extensions["geoip"] = FakeGeoIP(
            country=None,
            error="geoip_unavailable",
        )
        app.config["GEOIP_FAIL_MODE"] = "closed"

    response = login(client, "admin", "AdminPass123!")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "GEOIP_UNAVAILABLE"
