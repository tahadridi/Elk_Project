import time
import urllib.request

from flask import Blueprint, current_app, jsonify

from ..extensions import get_db, get_es, get_redis

bp = Blueprint("health", __name__)


def _timed(check):
    started = time.perf_counter()
    try:
        detail = check()
        return {
            "status": "up",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            **detail,
        }
    except Exception as exc:
        return {
            "status": "down",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": str(exc),
        }


def _mongo_check():
    get_db().command("ping")
    return {}


def _redis_check():
    get_redis().ping()
    return {}


def _elasticsearch_check():
    es = get_es()
    es.ping()
    health = es.cluster.health(request_timeout=1)
    return {"cluster_status": health.get("status")}


def _logstash_check():
    with urllib.request.urlopen(
        f"{current_app.config['LOGSTASH_URL']}/", timeout=2
    ) as response:
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")
    return {}


@bp.get("/health")
def health():
    checks = {
        "mongodb": _timed(_mongo_check),
        "redis": _timed(_redis_check),
        "elasticsearch": _timed(_elasticsearch_check),
        "logstash": _timed(_logstash_check),
    }
    critical = ["mongodb", "redis", "elasticsearch"]
    if any(checks[name]["status"] != "up" for name in critical):
        status = "down"
        code = 503
    elif checks["logstash"]["status"] != "up":
        status = "degraded"
        code = 200
    else:
        status = "healthy"
        code = 200

    return jsonify({"status": status, "checks": checks}), code
