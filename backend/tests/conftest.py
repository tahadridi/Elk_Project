import mongomock
import fakeredis
import pytest

from app import create_app
from app.services.auth_service import create_user


class FakeCluster:
    def health(self, **_kwargs):
        return {"status": "green"}


class FakeES:
    def __init__(self):
        self.cluster = FakeCluster()

    def ping(self):
        return True

    def count(self, **_kwargs):
        return {"count": 0}

    def search(self, **_kwargs):
        return {"hits": {"total": {"value": 0}, "hits": []}}


class FakeGeoIP:
    def __init__(self, country=None, is_private=False, error=None):
        self.country = country
        self.is_private = is_private
        self.error = error

    def lookup(self, _ip):
        result = {"country": self.country, "is_private": self.is_private}
        if self.error:
            result["error"] = self.error
        return result


@pytest.fixture
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SEED_DEFAULTS": True,
            "GEOIP_ENFORCEMENT_ENABLED": False,
            "GEOIP_DB_PATH": str(tmp_path / "missing.mmdb"),
            "UPLOAD_DIR": str(tmp_path / "input"),
            "MAX_UPLOAD_MB": 5,
            "JWT_SECRET_KEY": "test-jwt-secret-with-at-least-32-bytes",
            "SECRET_KEY": "test-flask-secret-with-at-least-32-bytes",
        },
        mongo_client=mongomock.MongoClient(),
        redis_client=fakeredis.FakeRedis(decode_responses=True),
        es_client=FakeES(),
    )
    with application.app_context():
        create_user("admin", "AdminPass123!", "admin", created_by="test")
        create_user("analyst", "AnalystPass123!", "analyst", created_by="test")
        create_user("user", "UserPass123!", "user", created_by="test")
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username, password):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    return response


@pytest.fixture
def admin_headers(client):
    response = login(client, "admin", "AdminPass123!")
    assert response.status_code == 200, response.get_json()
    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers(client):
    response = login(client, "user", "UserPass123!")
    assert response.status_code == 200, response.get_json()
    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
