from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

from ..services.auth_service import (
    authenticate,
    get_user_by_id,
    public_user,
    update_last_login,
)
from ..services.geoip_service import get_geoip_service
from ..services.mongo import record_security_event
from ..services.policy_service import (
    evaluate_country,
    get_auth_policy,
    get_geo_policy,
)
from ..services.redis_client import (
    block_ttl,
    is_blocked,
    record_failure,
    reset_failures,
)
from ..utils.responses import error_response
from ..utils.validators import get_client_ip

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", ""))
    ip = get_client_ip(request, current_app.config["TRUSTED_PROXIES"])

    if is_blocked(ip):
        record_security_event(
            "login_blocked_ip",
            username=username,
            ip=ip,
            reason="ip_blocked",
        )
        return error_response(
            "IP_BLOCKED",
            "Too many failed attempts. Try again later.",
            429,
            {"retry_after_seconds": block_ttl(ip)},
        )

    country = None
    is_private = False
    geo_policy = get_geo_policy()
    if geo_policy.get("enabled", True):
        geo = get_geoip_service().lookup(ip)
        country = geo.get("country")
        is_private = bool(geo.get("is_private"))
        if geo.get("error") == "geoip_unavailable":
            if current_app.config["GEOIP_FAIL_MODE"] == "closed":
                record_security_event(
                    "login_blocked_geoip_unavailable",
                    username=username,
                    ip=ip,
                    reason=geo.get("error"),
                )
                return error_response(
                    "GEOIP_UNAVAILABLE",
                    "Login is temporarily unavailable. Please try again later.",
                    503,
                )
        else:
            allowed, reason = evaluate_country(country, is_private)
            if not allowed:
                record_security_event(
                    "login_blocked_country",
                    username=username,
                    ip=ip,
                    country=country,
                    reason=reason,
                )
                return error_response(
                    "COUNTRY_BLOCKED",
                    "Login denied from this location.",
                    403,
                )

    user = authenticate(username, password)
    if user is None:
        auth_policy = get_auth_policy()
        count, blocked = record_failure(
            ip,
            auth_policy["max_failures"],
            auth_policy["block_minutes"],
        )
        record_security_event(
            "login_failed",
            username=username,
            ip=ip,
            country=country,
            reason="invalid_credentials",
            failure_count=count,
        )
        if blocked:
            record_security_event(
                "ip_blocked",
                username=username,
                ip=ip,
                reason="max_failures",
                failure_count=count,
            )
            return error_response(
                "IP_BLOCKED",
                "Too many failed attempts. Try again later.",
                429,
                {"retry_after_seconds": auth_policy["block_minutes"] * 60},
            )
        remaining = max(auth_policy["max_failures"] - count, 0)
        return error_response(
            "INVALID_CREDENTIALS",
            "Invalid username or password.",
            401,
            {"remaining_attempts": remaining},
        )

    reset_failures(ip)
    update_last_login(user["_id"])
    record_security_event(
        "login_success",
        username=user["username"],
        role=user["role"],
        ip=ip,
        country=country,
        is_private=is_private,
    )
    token = create_access_token(
        identity=str(user["_id"]),
        additional_claims={
            "username": user["username"],
            "role": user["role"],
        },
    )
    return jsonify({"access_token": token, "user": public_user(user)}), 200


@bp.post("/logout")
@jwt_required()
def logout():
    claims = get_jwt()
    record_security_event(
        "logout",
        username=claims.get("username"),
        user_id=get_jwt_identity(),
    )
    return jsonify({"message": "Logged out"}), 200


@bp.get("/me")
@jwt_required()
def me():
    user = get_user_by_id(get_jwt_identity())
    if user is None:
        return error_response("USER_NOT_FOUND", "User not found", 404)
    return jsonify({"user": public_user(user)}), 200
