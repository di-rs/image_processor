from fastapi.testclient import TestClient


def test_reserve_upload(client: TestClient) -> None:
    response = client.post(
        "/images",
        json={"filename": "cat.png", "content_type": "image/png"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["upload_url"].startswith("/images/uploads/")
    assert body["upload_expires_at"]
    assert "upload_token" not in body
    assert "storage_path" not in body
