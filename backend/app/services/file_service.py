import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app

from ..extensions import get_db, get_es
from ..utils.validators import safe_filename, validate_file
from .mongo import utcnow

logger = logging.getLogger(__name__)


def _upload_dir():
    path = Path(current_app.config["UPLOAD_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def _serialize_file(document):
    return {
        "file_id": document["file_id"],
        "original_name": document.get("original_name"),
        "stored_name": document.get("stored_name"),
        "format": document.get("format"),
        "size": document.get("size", 0),
        "status": document.get("status", "queued"),
        "log_count": document.get("log_count", 0),
        "expected_log_count": document.get("expected_log_count", 0),
        "uploaded_by": document.get("uploaded_by"),
        "uploaded_at": document.get("uploaded_at"),
    }


def preview_file(file_storage):
    max_bytes = current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024
    return validate_file(file_storage, max_bytes)


def save_upload(file_storage, user_id, username):
    max_bytes = current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024
    validation = validate_file(file_storage, max_bytes)

    file_id = uuid.uuid4().hex[:12]
    original_name = file_storage.filename or "upload"
    stored_name = f"{file_id}_{safe_filename(original_name)}"
    destination = _upload_dir() / stored_name

    file_storage.stream.seek(0)
    file_storage.save(destination)

    document = {
        "file_id": file_id,
        "original_name": original_name,
        "stored_name": stored_name,
        "format": validation["format"],
        "size": validation["size"],
        "status": "queued",
        "log_count": 0,
        "expected_log_count": validation["log_count"],
        "columns": validation.get("columns", []),
        "uploaded_by": username,
        "uploaded_by_id": user_id,
        "uploaded_at": utcnow(),
    }
    get_db().uploaded_files.insert_one(document)
    return _serialize_file(document)


def list_uploads(filters, page, per_page, sort="uploaded_at", order="desc"):
    query = {}
    if filters.get("status"):
        query["status"] = filters["status"]
    if filters.get("format"):
        query["format"] = filters["format"].lower()
    if filters.get("date_from") or filters.get("date_to"):
        date_filter = {}
        if filters.get("date_from"):
            date_filter["$gte"] = filters["date_from"]
        if filters.get("date_to"):
            date_filter["$lte"] = filters["date_to"]
        query["uploaded_at"] = date_filter

    sort_field = sort if sort in {"uploaded_at", "size", "status", "original_name"} else "uploaded_at"
    direction = -1 if str(order).lower() == "desc" else 1
    total = get_db().uploaded_files.count_documents(query)
    cursor = (
        get_db()
        .uploaded_files.find(query)
        .sort(sort_field, direction)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    return [_serialize_file(item) for item in cursor], total


def get_upload(file_id, refresh=False):
    document = get_db().uploaded_files.find_one({"file_id": file_id})
    if document is None:
        return None
    if refresh:
        document = sync_status(document)
    return _serialize_file(document)


def sync_status(document):
    try:
        result = get_es().count(
            index=current_app.config["ELASTIC_INDEX"],
            query={"term": {"file_id": document["file_id"]}},
        )
        count = int(result.get("count", 0))
    except Exception:
        logger.warning("Unable to refresh ingestion status for %s", document["file_id"], exc_info=True)
        return document

    updates = {}
    if count > 0:
        updates = {"status": "completed", "log_count": count}
    else:
        uploaded_at = document.get("uploaded_at")
        if isinstance(uploaded_at, datetime):
            if uploaded_at.tzinfo is None:
                uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - uploaded_at).total_seconds()
            if age > 300 and document.get("status") == "queued":
                updates = {"status": "failed"}

    if updates:
        get_db().uploaded_files.update_one(
            {"file_id": document["file_id"]},
            {"$set": updates},
        )
        document.update(updates)
    return document
