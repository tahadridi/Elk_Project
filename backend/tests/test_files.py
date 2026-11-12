import io


CSV = b"timestamp,level,service,message\n2026-01-01T00:00:00Z,INFO,auth,ok\n"


def test_preview_csv(client, admin_headers):
    response = client.post(
        "/api/v1/files/preview",
        headers=admin_headers,
        data={"file": (io.BytesIO(CSV), "logs.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["format"] == "csv"
    assert data["log_count"] == 1
    assert len(data["preview"]) >= 2


def test_upload_and_list(client, admin_headers):
    response = client.post(
        "/api/v1/files/upload",
        headers=admin_headers,
        data={"file": (io.BytesIO(CSV), "logs.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 202
    file_id = response.get_json()["data"]["file_id"]

    response = client.get("/api/v1/files", headers=admin_headers)
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert any(item["file_id"] == file_id for item in items)

    response = client.get(f"/api/v1/files/{file_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.get_json()["data"]["format"] == "csv"


def test_user_cannot_upload(client, user_headers):
    response = client.post(
        "/api/v1/files/upload",
        headers=user_headers,
        data={"file": (io.BytesIO(CSV), "logs.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 403
