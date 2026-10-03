from collections.abc import Callable
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from dramatiq import Message
from dramatiq.errors import ConnectionClosed
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from image_processor.broker import IMAGE_PROCESSING_QUEUE
from image_processor.domain.blob_key import BlobKey
from image_processor.models import Image, ProcessingStatus, utc_now
from image_processor.services.blob_storage import BlobStorage
from image_processor.workers.image_processing import process_message


def test_upload_stores_bytes_and_publishes_after_commit(
    client: TestClient,
    session: Session,
    blob_storage: BlobStorage,
    broker: MagicMock,
    reserve_upload: Callable[..., str],
) -> None:
    url = reserve_upload()

    def check_publish(message: Message) -> None:
        image = session.exec(select(Image)).one()
        assert message.queue_name == IMAGE_PROCESSING_QUEUE
        assert message.actor_name == process_message.actor_name
        assert message.args == (image.id,)
        assert message.kwargs == {}
        assert image.status == ProcessingStatus.uploaded
        assert image.upload_expires_at is None
        assert image.blob_key is not None
        assert (blob_storage.path / image.blob_key).read_bytes() == b"abc"

    broker.enqueue.side_effect = check_publish
    response = client.put(url, content=b"abc")
    assert response.status_code == 204
    assert response.content == b""
    image = session.exec(select(Image)).one()
    session.refresh(image)
    assert image.status == ProcessingStatus.queued
    broker.enqueue.assert_called_once()
    assert broker.enqueue.call_args.args[0].args == (image.id,)
    assert image.width is None
    assert image.height is None


def test_upload_url_cannot_be_reused(
    client: TestClient,
    session: Session,
    blob_storage: BlobStorage,
    broker: MagicMock,
    reserve_upload: Callable[..., str],
) -> None:
    url = reserve_upload()
    response = client.put(url, content=b"abc")
    assert response.status_code == 204
    image = session.exec(select(Image)).one()
    assert image.blob_key is not None

    response = client.put(url, content=b"xyz")
    assert response.status_code == 409
    assert response.json() == {"detail": "Upload URL has already been used"}
    assert (blob_storage.path / image.blob_key).read_bytes() == b"abc"
    session.refresh(image)
    assert image.status == ProcessingStatus.queued
    broker.enqueue.assert_called_once()
    assert broker.enqueue.call_args.args[0].args == (image.id,)


def test_publish_failure_preserves_upload(
    client: TestClient,
    session: Session,
    blob_storage: BlobStorage,
    broker: MagicMock,
    reserve_upload: Callable[..., str],
) -> None:
    url = reserve_upload()
    broker.enqueue.side_effect = ConnectionClosed("RabbitMQ unavailable")
    # TestClient propagates unhandled exceptions rather than returning HTTP 500.
    with pytest.raises(ConnectionClosed):
        client.put(url, content=b"abc")
    image = session.exec(select(Image)).one()
    session.refresh(image)
    assert image.status == ProcessingStatus.uploaded
    assert image.upload_expires_at is None
    assert image.blob_key is not None
    assert (blob_storage.path / image.blob_key).read_bytes() == b"abc"
    broker.enqueue.assert_called_once()
    assert broker.enqueue.call_args.args[0].args == (image.id,)


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (b"ab", "Uploaded bytes do not match the declared size"),
        (b"abcd", "Uploaded bytes exceed the declared size"),
    ],
)
def test_wrong_size_removes_image_and_temporary_bytes(
    client: TestClient,
    session: Session,
    blob_storage: BlobStorage,
    broker: MagicMock,
    reserve_upload: Callable[..., str],
    body: bytes,
    detail: str,
) -> None:
    url = reserve_upload()
    response = client.put(url, content=body)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    assert session.exec(select(Image)).all() == []
    assert list(blob_storage.path.iterdir()) == []
    broker.enqueue.assert_not_called()
    response = client.put(url, content=b"abc")
    assert response.status_code == 404
    assert response.json() == {"detail": "Upload not found"}


def test_expired_upload_is_removed_without_publishing(
    client: TestClient,
    session: Session,
    blob_storage: BlobStorage,
    broker: MagicMock,
    reserve_upload: Callable[..., str],
) -> None:
    url = reserve_upload()
    image = session.exec(select(Image)).one()
    image.upload_expires_at = utc_now() - timedelta(seconds=1)
    session.add(image)
    session.commit()

    response = client.put(url, content=b"abc")
    assert response.status_code == 410
    assert response.json() == {"detail": "Upload URL has expired"}
    assert session.exec(select(Image)).all() == []
    assert list(blob_storage.path.iterdir()) == []
    broker.enqueue.assert_not_called()


def test_already_claimed_upload_is_not_modified(
    client: TestClient,
    session: Session,
    broker: MagicMock,
    reserve_upload: Callable[..., str],
) -> None:
    url = reserve_upload()
    image = session.exec(select(Image)).one()
    image.status = ProcessingStatus.uploading
    session.add(image)
    session.commit()

    response = client.put(url, content=b"abc")
    assert response.status_code == 409
    assert response.json() == {"detail": "Upload URL has already been used"}
    session.refresh(image)
    assert image.status == ProcessingStatus.uploading
    broker.enqueue.assert_not_called()


def test_original_url_becomes_available_after_upload(
    client: TestClient,
    session: Session,
    reserve_upload: Callable[..., str],
) -> None:
    upload_url = reserve_upload()
    image = session.exec(select(Image)).one()
    response = client.get(f"/images/{image.id}")
    assert response.status_code == 200
    assert response.json()["original_url"] is None
    response = client.get(f"/images/{image.id}/original")
    assert response.status_code == 404
    assert response.json() == {"detail": "Image bytes not available"}

    response = client.put(upload_url, content=b"abc")
    assert response.status_code == 204
    response = client.get(f"/images/{image.id}")
    assert response.status_code == 200
    original_url = response.json()["original_url"]
    assert original_url == f"http://testserver/images/{image.id}/original"
    response = client.get("/images")
    assert response.status_code == 200
    images = response.json()
    assert len(images) == 1
    assert images[0]["id"] == image.id
    assert images[0]["original_url"] == original_url

    response = client.get(original_url)
    assert response.status_code == 200
    assert response.content == b"abc"
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_delete_uploaded_image_removes_stored_bytes(
    client: TestClient,
    session: Session,
    blob_storage: BlobStorage,
    reserve_upload: Callable[..., str],
) -> None:
    url = reserve_upload()
    response = client.put(url, content=b"abc")
    assert response.status_code == 204
    image = session.exec(select(Image)).one()
    assert image.blob_key is not None
    path = blob_storage.path / image.blob_key
    assert path.exists()

    response = client.delete(f"/images/{image.id}")
    assert response.status_code == 204
    assert response.content == b""
    assert not path.exists()
    assert session.exec(select(Image)).all() == []
    response = client.get(f"/images/{image.id}")
    assert response.status_code == 404


def test_unknown_upload_returns_404(
    client: TestClient, broker: MagicMock
) -> None:
    response = client.put(f"/images/uploads/{BlobKey.create()}", content=b"abc")
    assert response.status_code == 404
    assert response.json() == {"detail": "Upload not found"}
    broker.enqueue.assert_not_called()
