import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from image_processor.models import Image


@pytest.mark.parametrize(
    "filename", ["photo.svg", "photo.gif", "notes.txt", "unknown", "   "]
)
def test_invalid_upload_metadata_uses_domain_handler(
    client: TestClient, session: Session, filename: str
) -> None:
    response = client.post(
        "/images/uploads", json={"filename": filename, "size_bytes": 100}
    )
    assert response.status_code == 422
    assert "detail" in response.json()
    assert session.exec(select(Image)).all() == []
