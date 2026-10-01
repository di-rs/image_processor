from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from image_processor.domain.blob_key import BlobKey
from image_processor.main import app
from image_processor.models import Image, ProcessingStatus, utc_now
from image_processor.services.blob_storage import BlobStorage, get_blob_storage


@pytest.fixture
def storage(client: TestClient, tmp_path: Path) -> BlobStorage:
    storage = BlobStorage(tmp_path)
    app.dependency_overrides[get_blob_storage] = lambda: storage
    return storage


def reserve(client: TestClient, size: int) -> str:
    response = client.post(
        "/images/uploads", json={"filename": "photo.png", "size_bytes": size}
    )
    assert response.status_code == 201
    return response.json()["upload_url"]


def test_upload_and_reuse(
    client: TestClient, session: Session, storage: BlobStorage
) -> None:
    url = reserve(client, 3)
    assert client.put(url, content=b"abc").status_code == 204
    image = session.exec(select(Image)).one()
    assert image.status == ProcessingStatus.uploaded
    assert image.blob_key is not None
    assert (storage.path / image.blob_key).read_bytes() == b"abc"
    assert image.width is None
    assert client.put(url, content=b"xyz").status_code == 409
    assert (storage.path / image.blob_key).read_bytes() == b"abc"


@pytest.mark.parametrize("body", [b"ab", b"abcd"])
def test_wrong_size_removes_image(
    client: TestClient, session: Session, storage: BlobStorage, body: bytes
) -> None:
    url = reserve(client, 3)
    assert client.put(url, content=body).status_code == 422
    assert session.exec(select(Image)).all() == []
    assert list(storage.path.iterdir()) == []
    assert client.put(url, content=b"abc").status_code == 404


def test_expired_upload(
    client: TestClient, session: Session, storage: BlobStorage
) -> None:
    url = reserve(client, 3)
    image = session.exec(select(Image)).one()
    image.upload_expires_at = utc_now() - timedelta(seconds=1)
    session.add(image)
    session.commit()
    assert client.put(url, content=b"abc").status_code == 410
    assert session.exec(select(Image)).all() == []


def test_already_claimed_upload(
    client: TestClient, session: Session, storage: BlobStorage
) -> None:
    url = reserve(client, 3)
    image = session.exec(select(Image)).one()
    image.status = ProcessingStatus.uploading
    session.add(image)
    session.commit()
    assert client.put(url, content=b"abc").status_code == 409
    assert (
        session.exec(select(Image)).one().status == ProcessingStatus.uploading
    )


def test_public_original_url(
    client: TestClient, session: Session, storage: BlobStorage
) -> None:
    upload_url = reserve(client, 3)
    image = session.exec(select(Image)).one()
    assert client.get(f"/images/{image.id}").json()["original_url"] is None
    assert client.get(f"/images/{image.id}/original").status_code == 404
    assert client.put(upload_url, content=b"abc").status_code == 204
    original_url = client.get(f"/images/{image.id}").json()["original_url"]
    assert client.get("/images").json()[0]["original_url"] == original_url
    response = client.get(original_url)
    assert response.status_code == 200
    assert response.content == b"abc"
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_upload_then_delete(
    client: TestClient, session: Session, storage: BlobStorage
) -> None:
    url = reserve(client, 3)
    assert client.put(url, content=b"abc").status_code == 204
    image = session.exec(select(Image)).one()
    path = storage.path / str(image.blob_key)
    assert path.exists()
    assert client.delete(f"/images/{image.id}").status_code == 204
    assert not path.exists()
    assert session.exec(select(Image)).all() == []



def test_unknown_upload(client: TestClient, storage: BlobStorage) -> None:
    assert (
        client.put(
            f"/images/uploads/{BlobKey.create()}", content=b"abc"
        ).status_code
        == 404
    )
