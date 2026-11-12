from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from ..services.file_service import (
    get_upload,
    list_uploads,
    preview_file,
    save_upload,
)
from ..utils.responses import (
    error_response,
    paginated,
    parse_pagination,
    success_response,
)
from ..utils.security import roles_required
from ..utils.validators import ValidationError

bp = Blueprint("files", __name__, url_prefix="/api/v1/files")


def _parse_date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Date filters must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@bp.post("/preview")
@roles_required("admin", "analyst")
def preview():
    file_storage = request.files.get("file")
    if file_storage is None:
        return error_response("MISSING_FILE", "A file is required", 400)
    try:
        details = preview_file(file_storage)
    except ValidationError as exc:
        return error_response("INVALID_FILE", str(exc), 400)
    return success_response(details)


@bp.post("/upload")
@roles_required("admin", "analyst")
def upload():
    file_storage = request.files.get("file")
    if file_storage is None:
        return error_response("MISSING_FILE", "A file is required", 400)
    try:
        result = save_upload(
            file_storage,
            user_id=get_jwt_identity(),
            username=get_jwt().get("username"),
        )
    except ValidationError as exc:
        return error_response("INVALID_FILE", str(exc), 400)
    except OSError:
        return error_response("STORAGE_ERROR", "Unable to save the uploaded file", 500)
    return success_response(result, status=202)


@bp.get("")
@jwt_required()
def list_files():
    page, per_page = parse_pagination(default_per_page=20)
    try:
        date_from = _parse_date(request.args.get("date_from"))
        date_to = _parse_date(request.args.get("date_to"))
    except ValueError as exc:
        return error_response("INVALID_DATE", str(exc), 400)

    items, total = list_uploads(
        {
            "status": request.args.get("status"),
            "format": request.args.get("format"),
            "date_from": date_from,
            "date_to": date_to,
        },
        page,
        per_page,
        sort=request.args.get("sort", "uploaded_at"),
        order=request.args.get("order", "desc"),
    )
    return jsonify(paginated(items, total, page, per_page)), 200


@bp.get("/<file_id>")
@jwt_required()
def file_detail(file_id):
    refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
    item = get_upload(file_id, refresh=refresh)
    if item is None:
        return error_response("FILE_NOT_FOUND", "Uploaded file not found", 404)
    return success_response(item)
