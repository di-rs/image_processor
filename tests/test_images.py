from fastapi.testclient import TestClient


def test_create_upload_target(client: TestClient) -> None:
    response = client.post(
        "/images",
        json={"filename": "cat.png", "content_type": "image/png"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["upload_url"].startswith("/images/uploads/")
    assert "id" not in body
    assert "blob_key" not in body
