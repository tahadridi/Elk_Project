import io

import pytest
from werkzeug.datastructures import FileStorage

from app.utils.validators import ValidationError, validate_file


def storage(content, filename):
    return FileStorage(
        stream=io.BytesIO(content.encode("utf-8")),
        filename=filename,
        content_type="text/plain",
    )


def test_valid_csv():
    result = validate_file(
        storage("timestamp,level,message\n2026-01-01T00:00:00Z,INFO,ok\n", "logs.csv"),
        1024 * 1024,
    )
    assert result["format"] == "csv"
    assert result["log_count"] == 1
    assert result["columns"] == ["timestamp", "level", "message"]


def test_invalid_csv_columns():
    with pytest.raises(ValidationError):
        validate_file(
            storage("a,b,c\n1,2\n", "logs.csv"),
            1024 * 1024,
        )


def test_valid_ndjson():
    result = validate_file(
        storage('{"level":"INFO","message":"ok"}\n{"level":"ERROR","message":"bad"}\n', "logs.json"),
        1024 * 1024,
    )
    assert result["format"] == "json"
    assert result["log_count"] == 2


def test_invalid_json():
    with pytest.raises(ValidationError):
        validate_file(storage("{broken\n", "logs.json"), 1024 * 1024)


def test_valid_txt():
    result = validate_file(
        storage("line one\nline two\n", "logs.txt"),
        1024 * 1024,
    )
    assert result["format"] == "txt"
    assert result["log_count"] == 2


def test_rejects_unsupported_extension():
    with pytest.raises(ValidationError):
        validate_file(storage("hello", "logs.exe"), 1024 * 1024)


def test_rejects_too_large_file():
    with pytest.raises(ValidationError):
        validate_file(storage("a\nb\n", "logs.txt"), 1)
