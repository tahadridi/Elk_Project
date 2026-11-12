import re

import pycountry
from flask import current_app

from ..extensions import get_db
from .mongo import default_settings, record_security_event, utcnow

COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
VALID_ROLES = {"admin", "analyst", "user"}
VALID_SECTIONS = {"auth", "geo", "uploads", "search"}
VALID_MODES = {"allowlist", "blocklist"}
VALID_UNKNOWN_ACTIONS = {"allow", "deny"}


def _bool_value(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _merged_section(section):
    defaults = default_settings()[section]
    stored = get_db().settings.find_one({"_id": section}) or {}
    merged = dict(defaults)
    merged.update({key: value for key, value in stored.items() if key != "_id"})
    return merged


def get_section(section):
    if section not in VALID_SECTIONS:
        raise ValueError("Unknown settings section")
    return _merged_section(section)


def get_auth_policy():
    return _merged_section("auth")


def get_geo_policy():
    policy = _merged_section("geo")
    policy["allowed_countries"] = [
        str(item).upper() for item in policy.get("allowed_countries", [])
    ]
    policy["blocked_countries"] = [
        str(item).upper() for item in policy.get("blocked_countries", [])
    ]
    return policy


def get_upload_policy():
    return _merged_section("uploads")


def get_search_policy():
    return _merged_section("search")


def _clean_country_list(values):
    if not isinstance(values, list):
        raise ValueError("Country list must be an array")
    cleaned = []
    for value in values:
        code = str(value).strip().upper()
        if not COUNTRY_RE.match(code):
            raise ValueError(f"Invalid country code: {value}")
        if pycountry.countries.get(alpha_2=code) is None:
            raise ValueError(f"Unknown ISO country code: {value}")
        if code not in cleaned:
            cleaned.append(code)
    return cleaned


def validate_section(section, values):
    if section not in VALID_SECTIONS:
        raise ValueError("Unknown settings section")
    if not isinstance(values, dict):
        raise ValueError("Settings payload must be an object")

    if section == "auth":
        max_failures = int(values.get("max_failures", 0))
        block_minutes = int(values.get("block_minutes", 0))
        if not 1 <= max_failures <= 100:
            raise ValueError("max_failures must be between 1 and 100")
        if not 1 <= block_minutes <= 1440:
            raise ValueError("block_minutes must be between 1 and 1440")
        return {"max_failures": max_failures, "block_minutes": block_minutes}

    if section == "geo":
        mode = str(values.get("mode", "allowlist")).strip().lower()
        unknown = str(values.get("unknown_country", "deny")).strip().lower()
        if mode not in VALID_MODES:
            raise ValueError("mode must be allowlist or blocklist")
        if unknown not in VALID_UNKNOWN_ACTIONS:
            raise ValueError("unknown_country must be allow or deny")
        allowed = _clean_country_list(values.get("allowed_countries", []))
        blocked = _clean_country_list(values.get("blocked_countries", []))
        enabled = _bool_value(values.get("enabled", True), True)
        allow_private = _bool_value(values.get("allow_private_ips", True), True)
        if enabled and mode == "allowlist" and not allowed:
            raise ValueError("allowlist mode requires at least one allowed country")
        return {
            "enabled": enabled,
            "mode": mode,
            "allowed_countries": allowed,
            "blocked_countries": blocked,
            "unknown_country": unknown,
            "allow_private_ips": allow_private,
        }

    if section == "uploads":
        max_size_mb = int(values.get("max_size_mb", 0))
        extensions = values.get("allowed_extensions", [])
        if not 1 <= max_size_mb <= 1024:
            raise ValueError("max_size_mb must be between 1 and 1024")
        if not isinstance(extensions, list):
            raise ValueError("allowed_extensions must be an array")
        cleaned = []
        for extension in extensions:
            normalized = str(extension).strip().lower().lstrip(".")
            if normalized not in {"csv", "json", "txt"}:
                raise ValueError(f"Unsupported extension: {extension}")
            if normalized not in cleaned:
                cleaned.append(normalized)
        if not cleaned:
            raise ValueError("At least one allowed extension is required")
        return {"max_size_mb": max_size_mb, "allowed_extensions": cleaned}

    page_size = int(values.get("page_size", 0))
    if not 1 <= page_size <= 200:
        raise ValueError("page_size must be between 1 and 200")
    return {"page_size": page_size}


def update_section(section, values, updated_by):
    current = get_section(section)
    cleaned = validate_section(section, {**current, **values})
    document = {
        **cleaned,
        "updated_by": updated_by,
        "updated_at": utcnow(),
    }
    get_db().settings.replace_one({"_id": section}, document, upsert=True)
    record_security_event(
        "settings_updated",
        username=updated_by,
        section=section,
        changed_fields=sorted(values.keys()),
    )
    return get_section(section)


def evaluate_country(country_code, is_private=False):
    policy = get_geo_policy()
    if not policy.get("enabled", True):
        return True, "enforcement_disabled"
    if is_private and policy.get("allow_private_ips", True):
        return True, "private_ip_allowed"

    code = (country_code or "").strip().upper()
    if not code:
        return policy.get("unknown_country", "deny") == "allow", "unknown_country"

    if policy.get("mode") == "blocklist":
        allowed = code not in set(policy.get("blocked_countries", []))
        return allowed, "country_allowed" if allowed else "country_blocked"

    allowed = code in set(policy.get("allowed_countries", []))
    return allowed, "country_allowed" if allowed else "country_not_allowed"


def list_countries():
    countries = [
        {"code": country.alpha_2, "name": country.name}
        for country in pycountry.countries
    ]
    return sorted(countries, key=lambda item: item["name"])
