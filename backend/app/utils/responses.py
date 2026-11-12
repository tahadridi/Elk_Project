from flask import jsonify, request


def error_response(code, message, status=400, details=None):
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return jsonify(payload), status


def success_response(data=None, status=200, **extra):
    payload = {}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload), status


def _int_arg(name, default, minimum=None, maximum=None):
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def parse_pagination(default_per_page=50, max_per_page=200):
    page = _int_arg("page", 1, minimum=1)
    per_page = _int_arg("per_page", default_per_page, minimum=1, maximum=max_per_page)
    return page, per_page


def paginated(items, total, page, per_page):
    pages = (total + per_page - 1) // per_page if per_page else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }
