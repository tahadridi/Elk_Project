import csv
import io
import ipaddress
import json
import os

from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"csv", "json", "txt"}


class ValidationError(ValueError):
    pass


def file_extension(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def allowed_file(filename: str) -> bool:
    return file_extension(filename) in ALLOWED_EXTENSIONS


def safe_filename(filename: str) -> str:
    cleaned = secure_filename(filename or "upload")
    return cleaned or "upload"


def file_size(file_storage) -> int:
    stream = file_storage.stream
    current = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(current)
    return size


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("File must be valid UTF-8 text") from exc


def _validate_csv(text: str):
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text), dialect)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValidationError("CSV file is empty") from exc

    if not header or not any(cell.strip() for cell in header):
        raise ValidationError("CSV header is missing")

    expected_columns = len(header)
    row_count = 0
    for line_number, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != expected_columns:
            raise ValidationError(
                f"CSV line {line_number} has {len(row)} columns, expected {expected_columns}"
            )
        row_count += 1

    if row_count == 0:
        raise ValidationError("CSV file contains no data rows")

    return {
        "columns": [cell.strip() for cell in header],
        "log_count": row_count,
    }


def _validate_json(text: str):
    stripped = text.lstrip()
    if not stripped:
        raise ValidationError("JSON file is empty")

    if stripped.startswith("["):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON at line {exc.lineno}: {exc.msg}") from exc
        if not isinstance(payload, list) or not payload:
            raise ValidationError("JSON array must contain at least one object")
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise ValidationError(f"JSON array item {index} is not an object")
        columns = list(payload[0].keys())
        return {"columns": columns, "log_count": len(payload)}

    count = 0
    columns = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"Invalid JSON line {line_number}: {exc.msg}"
            ) from exc
        if not isinstance(item, dict):
            raise ValidationError(f"JSON line {line_number} is not an object")
        if not columns:
            columns = list(item.keys())
        count += 1

    if count == 0:
        raise ValidationError("JSON file contains no objects")

    return {"columns": columns, "log_count": count}


def _validate_txt(text: str):
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValidationError("TXT file is empty")
    return {"columns": [], "log_count": len(lines)}


def validate_file(file_storage, max_size_bytes: int):
    filename = file_storage.filename or ""
    extension = file_extension(filename)

    if not allowed_file(filename):
        raise ValidationError("Unsupported file format. Allowed formats: CSV, JSON, TXT")

    size = file_size(file_storage)
    if size == 0:
        raise ValidationError("File is empty")
    if size > max_size_bytes:
        raise ValidationError(
            f"File is too large. Maximum size is {max_size_bytes // (1024 * 1024)} MB"
        )

    file_storage.stream.seek(0)
    raw = file_storage.stream.read()
    text = _decode(raw)

    if extension == "csv":
        details = _validate_csv(text)
    elif extension == "json":
        details = _validate_json(text)
    else:
        details = _validate_txt(text)

    preview_lines = text.splitlines()[:10]
    return {
        "filename": filename,
        "format": extension,
        "size": size,
        "preview": preview_lines,
        "warnings": [],
        **details,
    }


def get_client_ip(request, trusted_proxies=()):
    remote = (request.remote_addr or "").strip()
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded and remote in set(trusted_proxies):
        return forwarded.split(",")[0].strip()
    return remote


def is_private_ip(ip: str) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    )
