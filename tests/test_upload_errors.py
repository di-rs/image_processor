import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from image_processor.models import Image


@pytest.mark.parametrize(
    ("filename", "detail"),
    [
        (
            "photo.svg",
            "Content type must identify an image other than GIF or SVG",
        ),
        (
            "photo.gif",
            "Content type must identify an image other than GIF or SVG",
        ),
        (
            "notes.txt",
            "Content type must identify an image other than GIF or SVG",
        ),
        ("unknown", "Filename must identify an image other than GIF or SVG"),
    ],
)
def test_unsupported_upload_filename_uses_domain_handler(
    client: TestClient, session: Session, filename: str, detail: str
) -> None:
    response = client.post(
        "/images/uploads", json={"filename": filename, "size_bytes": 100}
    )
    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    assert session.exec(select(Image)).all() == []


@pytest.mark.parametrize("filename", ["", "   ", "\t\n", None, "a" * 256])
def test_invalid_upload_filename_uses_request_validation(
    client: TestClient, session: Session, filename: str | None
) -> None:
    response = client.post(
        "/images/uploads", json={"filename": filename, "size_bytes": 100}
    )
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert isinstance(errors, list)
    assert any(error["loc"] == ["body", "filename"] for error in errors)
    assert session.exec(select(Image)).all() == []


@pytest.mark.parametrize("size_bytes", [0, -1, None])
def test_invalid_upload_size_does_not_create_image(
    client: TestClient, session: Session, size_bytes: int | None
) -> None:
    response = client.post(
        "/images/uploads",
        json={"filename": "photo.png", "size_bytes": size_bytes},
    )
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error["loc"] == ["body", "size_bytes"] for error in errors)
    assert session.exec(select(Image)).all() == []
