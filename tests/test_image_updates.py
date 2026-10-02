from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import Session

from image_processor.models import Image, ImageUpdate, ImageUploadCreate


@pytest.mark.parametrize("filename", ["", " ", "\t\n", None])
def test_update_rejects_blank_filename(filename: str | None) -> None:
    with pytest.raises(ValidationError):
        ImageUpdate(filename=filename)


@pytest.mark.parametrize("filename", ["", " ", "\t\n"])
def test_upload_rejects_blank_filename(filename: str) -> None:
    with pytest.raises(ValidationError):
        ImageUploadCreate(filename=filename, size_bytes=100)


@pytest.mark.parametrize("field", ["filename", "content_type"])
@pytest.mark.parametrize("value", ["", " ", "\t\n", None])
def test_invalid_update_does_not_change_image(
    client: TestClient,
    session: Session,
    make_image: Callable[..., Image],
    field: str,
    value: str | None,
) -> None:
    image = make_image()
    response = client.patch(f"/images/{image.id}", json={field: value})
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error["loc"] == ["body", field] for error in errors)
    session.refresh(image)
    assert image.filename == "original.png"
    assert image.content_type == "image/png"


def test_filename_update_strips_whitespace(
    client: TestClient, session: Session, make_image: Callable[..., Image]
) -> None:
    image = make_image()
    response = client.patch(
        f"/images/{image.id}", json={"filename": " renamed.png "}
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "renamed.png"
    assert response.json()["id"] == image.id
    session.refresh(image)
    assert image.filename == "renamed.png"
    assert image.content_type == "image/png"


def test_content_type_update_preserves_omitted_filename(
    client: TestClient, session: Session, make_image: Callable[..., Image]
) -> None:
    image = make_image(filename="renamed.png")
    response = client.patch(
        f"/images/{image.id}", json={"content_type": "image/jpeg"}
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "renamed.png"
    assert response.json()["content_type"] == "image/jpeg"
    session.refresh(image)
    assert image.filename == "renamed.png"
    assert image.content_type == "image/jpeg"


def test_empty_update_preserves_image(
    client: TestClient, session: Session, make_image: Callable[..., Image]
) -> None:
    image = make_image()
    response = client.patch(f"/images/{image.id}", json={})
    assert response.status_code == 200
    assert response.json()["filename"] == "original.png"
    assert response.json()["content_type"] == "image/png"
    session.refresh(image)
    assert image.filename == "original.png"
    assert image.content_type == "image/png"
    assert ImageUpdate().model_dump(exclude_unset=True) == {}
