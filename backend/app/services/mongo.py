import logging
from datetime import datetime, timezone

from flask import current_app
from pymongo import ASCENDING, DESCENDING

from ..extensions import get_db

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


def ensure_indexes():
    db = get_db()
    db.users.create_index("username", unique=True)
    db.users.create_index("role")
    db.uploaded_files.create_index("file_id", unique=True)
    db.uploaded_files.create_index([("uploaded_at", DESCENDING)])
    db.search_history.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.security_events.create_index([("created_at", DESCENDING)])
    db.security_events.create_index([("event_type", ASCENDING)])
    db.security_events.create_index([("username", ASCENDING)])


def default_settings():
    app = current_app
    return {
        "auth": {
            "max_failures": app.config["LOGIN_MAX_FAILURES"],
            "block_minutes": app.config["LOGIN_BLOCK_MINUTES"],
        },
        "geo": {
            "enabled": app.config["GEOIP_ENFORCEMENT_ENABLED"],
            "mode": "allowlist",
            "allowed_countries": list(app.config["DEFAULT_ALLOWED_COUNTRIES"]),
            "blocked_countries": [],
            "unknown_country": "deny",
            "allow_private_ips": app.config["ALLOW_PRIVATE_IPS"],
        },
        "uploads": {
            "max_size_mb": app.config["MAX_UPLOAD_MB"],
            "allowed_extensions": ["csv", "json", "txt"],
        },
        "search": {"page_size": 50},
    }


def seed_default_settings():
    db = get_db()
    for section, values in default_settings().items():
        db.settings.update_one(
            {"_id": section},
            {
                "$setOnInsert": {
                    **values,
                    "updated_by": "system",
                    "updated_at": utcnow(),
                }
            },
            upsert=True,
        )


def record_security_event(event_type, **fields):
    try:
        document = {"event_type": event_type, "created_at": utcnow(), **fields}
        get_db().security_events.insert_one(document)
        return document
    except Exception:
        logger.exception("Unable to record security event %s", event_type)
        return None
