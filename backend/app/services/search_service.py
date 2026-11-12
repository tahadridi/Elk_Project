from datetime import datetime, timezone

from flask import current_app

from ..extensions import get_db, get_es
from .mongo import utcnow

SORT_FIELDS = {
    "date": "@timestamp",
    "timestamp": "@timestamp",
    "level": "log.level",
    "service": "service.name",
}
VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def parse_date(value, field_name):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 date") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def build_search_query(q=None, level=None, service=None, date_from=None, date_to=None):
    must = []
    filters = []

    if q:
        must.append(
            {
                "multi_match": {
                    "query": q,
                    "fields": [
                        "message",
                        "user.name",
                        "source.ip",
                        "service.name",
                        "event.action",
                    ],
                    "type": "best_fields",
                }
            }
        )

    if level:
        normalized = str(level).upper()
        if normalized not in VALID_LEVELS:
            raise ValueError(f"level must be one of: {', '.join(sorted(VALID_LEVELS))}")
        filters.append({"term": {"log.level": normalized}})

    if service:
        filters.append({"term": {"service.name": service}})

    start = parse_date(date_from, "date_from")
    end = parse_date(date_to, "date_to")
    if start or end:
        date_range = {}
        if start:
            date_range["gte"] = start
        if end:
            date_range["lte"] = end
        filters.append({"range": {"@timestamp": date_range}})

    if not must:
        must.append({"match_all": {}})

    return {"bool": {"must": must, "filter": filters}}


def serialize_hit(hit):
    source = hit.get("_source", {})
    return {
        "id": hit.get("_id"),
        "timestamp": source.get("@timestamp"),
        "level": (source.get("log") or {}).get("level"),
        "service": (source.get("service") or {}).get("name"),
        "message": source.get("message"),
        "source_ip": (source.get("source") or {}).get("ip"),
        "user": (source.get("user") or {}).get("name"),
        "event": source.get("event") or {},
        "file_id": source.get("file_id"),
        "tags": source.get("tags", []),
    }


def search_logs(q=None, level=None, service=None, date_from=None, date_to=None,
                page=1, per_page=50, sort="date", order="desc"):
    query = build_search_query(q, level, service, date_from, date_to)
    sort_field = SORT_FIELDS.get(str(sort).lower(), "@timestamp")
    sort_order = "asc" if str(order).lower() == "asc" else "desc"

    response = get_es().search(
        index=current_app.config["ELASTIC_INDEX"],
        query=query,
        from_=(page - 1) * per_page,
        size=per_page,
        sort=[{sort_field: {"order": sort_order}}],
        track_total_hits=True,
    )
    hits = response.get("hits", {})
    total = hits.get("total", {})
    if isinstance(total, dict):
        total = total.get("value", 0)
    return [serialize_hit(hit) for hit in hits.get("hits", [])], int(total or 0)


def get_log(log_id):
    response = get_es().search(
        index=current_app.config["ELASTIC_INDEX"],
        query={"ids": {"values": [log_id]}},
        size=1,
    )
    hits = response.get("hits", {}).get("hits", [])
    return serialize_hit(hits[0]) if hits else None


def export_logs(q=None, level=None, service=None, date_from=None, date_to=None,
                sort="date", order="desc"):
    query = build_search_query(q, level, service, date_from, date_to)
    sort_field = SORT_FIELDS.get(str(sort).lower(), "@timestamp")
    sort_order = "asc" if str(order).lower() == "asc" else "desc"
    limit = current_app.config["ELASTIC_EXPORT_LIMIT"]
    response = get_es().search(
        index=current_app.config["ELASTIC_INDEX"],
        query=query,
        size=limit,
        sort=[{sort_field: {"order": sort_order}}],
    )
    return [serialize_hit(hit) for hit in response.get("hits", {}).get("hits", [])]


def save_search_history(user_id, username, q, level, service, date_from, date_to):
    if not any([q, level, service, date_from, date_to]):
        return None
    document = {
        "user_id": user_id,
        "username": username,
        "query": q,
        "filters": {
            "level": level,
            "service": service,
            "date_from": date_from,
            "date_to": date_to,
        },
        "created_at": utcnow(),
    }
    get_db().search_history.insert_one(document)
    return document


def list_search_history(user_id, page, per_page):
    query = {"user_id": user_id}
    total = get_db().search_history.count_documents(query)
    cursor = (
        get_db()
        .search_history.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    items = []
    for item in cursor:
        items.append(
            {
                "id": str(item["_id"]),
                "query": item.get("query"),
                "filters": item.get("filters", {}),
                "created_at": item.get("created_at"),
            }
        )
    return items, total


def clear_search_history(user_id):
    result = get_db().search_history.delete_many({"user_id": user_id})
    return result.deleted_count


def get_stats():
    es = get_es()
    index = current_app.config["ELASTIC_INDEX"]
    error_index = current_app.config["ELASTIC_ERROR_INDEX"]

    total_logs = int(es.count(index=index, query={"match_all": {}}).get("count", 0))
    logs_today = int(
        es.count(
            index=index,
            query={"range": {"@timestamp": {"gte": "now/d", "lte": "now"}}},
        ).get("count", 0)
    )
    error_logs = int(
        es.count(
            index=index,
            query={"terms": {"log.level": ["ERROR", "CRITICAL"]}},
        ).get("count", 0)
    )
    parse_errors = int(
        es.count(index=error_index, query={"match_all": {}}).get("count", 0)
    )
    uploaded_files = int(get_db().uploaded_files.count_documents({}))

    return {
        "total_logs": total_logs,
        "logs_today": logs_today,
        "error_logs": error_logs,
        "parse_errors": parse_errors,
        "uploaded_files": uploaded_files,
    }
