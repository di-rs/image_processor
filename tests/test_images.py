from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from image_processor.models import Image, ProcessingStatus, utc_now


def test_get_image_returns_public_metadata(
    client: TestClient, make_image: Callable[..., Image]
) -> None:
    image = make_image()
    response = client.get(f"/images/{image.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == image.id
    assert data["filename"] == image.filename
    assert data["content_type"] == image.content_type
    assert data["size_bytes"] == image.size_bytes
    assert data["status"] == image.status.value
    assert data["width"] is None
    assert data["height"] is None
    assert data["original_url"] is None
    assert "created_at" in data
    assert "updated_at" in data
    assert "blob_key" not in data
    assert "upload_expires_at" not in data


def test_list_images_returns_empty_list(client: TestClient) -> None:
    response = client.get("/images")
    assert response.status_code == 200
    assert response.json() == []


def test_list_images_orders_newest_first_and_paginates(
    client: TestClient, session: Session, make_image: Callable[..., Image]
) -> None:
    images = [make_image(filename=f"image-{index}.png") for index in range(3)]
    # Distinct timestamps make ordering independent of clock resolution.
    base_time = utc_now() - timedelta(days=1)
    for index, image in enumerate(images):
        image.created_at = base_time + timedelta(seconds=index)
        session.add(image)
    session.commit()

    response = client.get("/images")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        image.id for image in reversed(images)
    ]

    response = client.get("/images", params={"limit": 1, "offset": 1})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [images[1].id]

    response = client.get("/images", params={"offset": 3})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "statuses",
    [
        [ProcessingStatus.finished],
        [ProcessingStatus.queued, ProcessingStatus.finished],
    ],
)
def test_list_images_filters_by_one_or_multiple_statuses(
    client: TestClient,
    make_image: Callable[..., Image],
    statuses: list[ProcessingStatus],
) -> None:
    images = [make_image(status=status) for status in ProcessingStatus]
    response = client.get(
        "/images", params=[("status", status.value) for status in statuses]
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(statuses)
    assert {item["id"] for item in data} == {
        image.id for image in images if image.status in statuses
    }
    assert {item["status"] for item in data} == {
        status.value for status in statuses
    }


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"status": "not-a-status"},
    ],
)
def test_list_images_rejects_invalid_query_parameters(
    client: TestClient, params: dict[str, int | str]
) -> None:
    response = client.get("/images", params=params)
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(
        error["loc"][:2] == ["query", next(iter(params))] for error in errors
    )


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_unknown_image_returns_404(client: TestClient, method: str) -> None:
    response = client.request(
        method, "/images/9999", json={"filename": "renamed.png"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Image not found."}


def test_delete_pending_image_removes_metadata(
    client: TestClient, session: Session, make_image: Callable[..., Image]
) -> None:
    image = make_image()
    image_id = image.id
    response = client.delete(f"/images/{image_id}")
    assert response.status_code == 204
    assert response.content == b""
    assert session.get(Image, image_id) is None
    response = client.get(f"/images/{image_id}")
    assert response.status_code == 404


def test_delete_active_upload_returns_conflict_and_preserves_image(
    client: TestClient, session: Session, make_image: Callable[..., Image]
) -> None:
    image = make_image(status=ProcessingStatus.uploading)
    response = client.delete(f"/images/{image.id}")
    assert response.status_code == 409
    assert response.json() == {"detail": "Cannot delete an active upload"}
    session.refresh(image)
    assert image.status == ProcessingStatus.uploading
    assert session.get(Image, image.id) is image
