import os
from datetime import timedelta


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-flask-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=env_int("JWT_ACCESS_TOKEN_MINUTES", 60))
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "security_monitoring")
    MONGO_TIMEOUT_MS = env_int("MONGO_TIMEOUT_MS", 2000)

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    ELASTIC_URL = os.getenv("ELASTIC_URL", "http://localhost:9200")
    ELASTIC_INDEX = os.getenv("ELASTIC_INDEX", "logs-security-*")
    ELASTIC_ERROR_INDEX = os.getenv("ELASTIC_ERROR_INDEX", "logs-parse-errors-*")
    ELASTIC_TIMEOUT = env_int("ELASTIC_TIMEOUT", 2)
    ELASTIC_EXPORT_LIMIT = env_int("ELASTIC_EXPORT_LIMIT", 10000)

    LOGSTASH_URL = os.getenv("LOGSTASH_URL", "http://localhost:9600")

    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/input")
    MAX_UPLOAD_MB = env_int("MAX_UPLOAD_MB", 100)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    ALLOWED_EXTENSIONS = {"csv", "json", "txt"}

    LOGIN_MAX_FAILURES = env_int("LOGIN_MAX_FAILURES", 5)
    LOGIN_BLOCK_MINUTES = env_int("LOGIN_BLOCK_MINUTES", 15)

    GEOIP_DB_PATH = os.getenv("GEOIP_DB_PATH", "/data/geoip/GeoLite2-Country.mmdb")
    GEOIP_ENFORCEMENT_ENABLED = env_bool("GEOIP_ENFORCEMENT_ENABLED", True)
    GEOIP_FAIL_MODE = os.getenv("GEOIP_FAIL_MODE", "open").strip().lower()
    DEFAULT_ALLOWED_COUNTRIES = [
        item.strip().upper()
        for item in os.getenv("DEFAULT_ALLOWED_COUNTRIES", "TN,FR,DE").split(",")
        if item.strip()
    ]
    ALLOW_PRIVATE_IPS = env_bool("ALLOW_PRIVATE_IPS", True)
    TRUSTED_PROXIES = [
        item.strip()
        for item in os.getenv("TRUSTED_PROXIES", "").split(",")
        if item.strip()
    ]

    SEED_DEFAULTS = env_bool("SEED_DEFAULTS", True)
