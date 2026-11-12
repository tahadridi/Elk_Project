import ipaddress
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity

from ..extensions import get_db
from ..services.auth_service import (
    create_user,
    list_users,
    public_user,
    update_user,
)
from ..services.geoip_service import get_geoip_service
from ..services.mongo import record_security_event, utcnow
from ..services.policy_service import (
    VALID_SECTIONS,
    evaluate_country,
    get_section,
    list_countries,
    update_section,
)
from ..services.redis_client import block_ip, list_blocked_ips, unblock_ip
from ..utils.responses import error_response, paginated, parse_pagination
from ..utils.security import roles_required
from ..utils.validators import get_client_ip

bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")


def _parse_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Date filters must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _bool_value(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@bp.get("/users")
@roles_required("admin")
def get_users():
    return jsonify({"users": list_users()}), 200


@bp.post("/users")
@roles_required("admin")
def post_user():
    data = request.get_json(silent=True) or {}
    try:
        user = create_user(
            data.get("username"),
            data.get("password"),
            data.get("role"),
            created_by=get_jwt().get("username"),
        )
    except ValueError as exc:
        return error_response("INVALID_USER", str(exc), 400)
    record_security_event(
        "user_created",
        username=get_jwt().get("username"),
        target_username=user["username"],
        role=user["role"],
    )
    return jsonify({"user": public_user(user)}), 201


@bp.patch("/users/<user_id>")
@roles_required("admin")
def patch_user(user_id):
    data = request.get_json(silent=True) or {}
    current_id = str(get_jwt_identity())
    if user_id == current_id and "active" in data and not _bool_value(data["active"], True):
        return error_response("INVALID_OPERATION", "You cannot deactivate your own account", 400)
    if "active" in data:
        data["active"] = _bool_value(data["active"], True)
    try:
        user = update_user(user_id, data, updated_by=get_jwt().get("username"))
    except ValueError as exc:
        return error_response("INVALID_USER", str(exc), 400)
    if user is None:
        return error_response("USER_NOT_FOUND", "User not found", 404)
    record_security_event(
        "user_updated",
        username=get_jwt().get("username"),
        target_username=user["username"],
        fields=sorted(data.keys()),
    )
    return jsonify({"user": public_user(user)}), 200


@bp.delete("/users/<user_id>")
@roles_required("admin")
def delete_user(user_id):
    current_id = str(get_jwt_identity())
    if user_id == current_id:
        return error_response("INVALID_OPERATION", "You cannot deactivate your own account", 400)
    try:
        user = update_user(user_id, {"active": False}, updated_by=get_jwt().get("username"))
    except ValueError as exc:
        return error_response("INVALID_USER", str(exc), 400)
    if user is None:
        return error_response("USER_NOT_FOUND", "User not found", 404)
    record_security_event(
        "user_deactivated",
        username=get_jwt().get("username"),
        target_username=user["username"],
    )
    return jsonify({"user": public_user(user)}), 200


@bp.get("/settings")
@roles_required("admin")
def get_settings():
    return jsonify({"settings": {section: get_section(section) for section in sorted(VALID_SECTIONS)}}), 200


@bp.put("/settings/<section>")
@roles_required("admin")
def put_settings(section):
    if section not in VALID_SECTIONS:
        return error_response("UNKNOWN_SECTION", "Unknown settings section", 404)
    data = request.get_json(silent=True) or {}
    try:
        updated = update_section(section, data, updated_by=get_jwt().get("username"))
    except (ValueError, TypeError) as exc:
        return error_response("INVALID_SETTINGS", str(exc), 400)

    warnings = []
    if section == "geo":
        ip = get_client_ip(request, current_app.config["TRUSTED_PROXIES"])
        geo = get_geoip_service().lookup(ip)
        allowed, reason = evaluate_country(geo.get("country"), geo.get("is_private", False))
        if not allowed:
            warnings.append(
                "The current admin location is not allowed by this policy. "
                "Keep GEOIP_ENFORCEMENT_ENABLED=false as an emergency fallback."
            )
            record_security_event(
                "geo_policy_admin_lockout_warning",
                username=get_jwt().get("username"),
                ip=ip,
                country=geo.get("country"),
                reason=reason,
            )

    return jsonify({"settings": updated, "warnings": warnings}), 200


@bp.get("/geo/countries")
@roles_required("admin")
def get_countries():
    return jsonify({"countries": list_countries()}), 200


@bp.get("/security-events")
@roles_required("admin")
def get_security_events():
    page, per_page = parse_pagination(default_per_page=50)
    query = {}
    if request.args.get("event_type"):
        query["event_type"] = request.args["event_type"]
    if request.args.get("username"):
        query["username"] = request.args["username"].strip().lower()
    if request.args.get("ip"):
        query["ip"] = request.args["ip"].strip()
    try:
        date_from = _parse_datetime(request.args.get("date_from"))
        date_to = _parse_datetime(request.args.get("date_to"))
    except ValueError as exc:
        return error_response("INVALID_DATE", str(exc), 400)
    if date_from or date_to:
        date_filter = {}
        if date_from:
            date_filter["$gte"] = date_from
        if date_to:
            date_filter["$lte"] = date_to
        query["created_at"] = date_filter

    collection = get_db().security_events
    total = collection.count_documents(query)
    cursor = (
        collection.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    items = []
    for item in cursor:
        items.append(
            {
                "id": str(item["_id"]),
                "event_type": item.get("event_type"),
                "username": item.get("username"),
                "ip": item.get("ip"),
                "country": item.get("country"),
                "reason": item.get("reason"),
                "created_at": item.get("created_at"),
                "details": {
                    key: value
                    for key, value in item.items()
                    if key
                    not in {
                        "_id",
                        "event_type",
                        "username",
                        "ip",
                        "country",
                        "reason",
                        "created_at",
                    }
                },
            }
        )
    return jsonify(paginated(items, total, page, per_page)), 200


@bp.get("/ip-blocks")
@roles_required("admin")
def get_ip_blocks():
    return jsonify({"blocks": list_blocked_ips()}), 200


@bp.post("/ip-blocks")
@roles_required("admin")
def post_ip_block():
    data = request.get_json(silent=True) or {}
    ip = str(data.get("ip", "")).strip()
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return error_response("INVALID_IP", "A valid IP address is required", 400)
    try:
        minutes = int(data.get("minutes", 15))
    except (TypeError, ValueError):
        return error_response("INVALID_DURATION", "minutes must be an integer", 400)
    if not 1 <= minutes <= 1440:
        return error_response("INVALID_DURATION", "minutes must be between 1 and 1440", 400)

    block_ip(ip, minutes)
    record_security_event(
        "ip_blocked_manually",
        username=get_jwt().get("username"),
        ip=ip,
        reason=data.get("reason") or "manual_block",
        minutes=minutes,
    )
    return jsonify({"ip": ip, "ttl_seconds": minutes * 60}), 201


@bp.delete("/ip-blocks/<ip>")
@roles_required("admin")
def delete_ip_block(ip):
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return error_response("INVALID_IP", "A valid IP address is required", 400)
    unblock_ip(ip)
    record_security_event(
        "ip_unblocked_manually",
        username=get_jwt().get("username"),
        ip=ip,
    )
    return jsonify({"ip": ip, "unblocked": True}), 200
