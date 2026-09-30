from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from image_processor.domain.images import (
    ImageStatus,
    InvalidImageStateError,
    PreuploadedImage,
    UploadedImage,
    UploadExpiredError,
)

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
TTL = timedelta(minutes=15)


def _reservation(**overrides: object) -> PreuploadedImage:
    values: dict[str, object] = {
        "filename": "cat.png",
        "content_type": "image/png",
        "storage_path": "/data/images/token",
        "ttl": TTL,
        "now": NOW,
    }
    values.update(overrides)
    return PreuploadedImage.create(**values)  # type: ignore[arg-type]


def test_create_reserves_a_token_and_expiry() -> None:
    reservation = _reservation()

    assert reservation.filename == "cat.png"
    assert reservation.content_type == "image/png"
    assert reservation.storage_path == "/data/images/token"
    assert reservation.upload_expires_at == NOW + TTL
    assert 1 <= len(reservation.upload_token) <= 64


def test_create_rejects_invalid_reservation_data() -> None:
    with pytest.raises(ValidationError):
        _reservation(filename="  ")


def test_upload_returns_an_uploaded_image() -> None:
    reservation = _reservation()

    image = reservation.upload(
        size_bytes=128,
        width=10,
        height=20,
        now=NOW,
    )

    assert isinstance(image, UploadedImage)
    assert image.status is ImageStatus.uploaded
    assert image.filename == reservation.filename
    assert image.storage_path == reservation.storage_path
    assert image.size_bytes == 128
    assert image.width == 10
    assert image.height == 20
    assert image.created_at == NOW
    assert image.updated_at == NOW
    assert not hasattr(image, "upload_token")


def test_upload_rejects_an_expired_token() -> None:
    reservation = _reservation()

    with pytest.raises(UploadExpiredError):
        reservation.upload(
            size_bytes=128,
            width=10,
            height=20,
            now=reservation.upload_expires_at,
        )


def test_enqueue_is_only_valid_after_upload() -> None:
    image = _reservation().upload(
        size_bytes=128,
        width=10,
        height=20,
        now=NOW,
    )
    queued_at = NOW + timedelta(seconds=1)

    queued = image.enqueue(now=queued_at)

    assert queued.status is ImageStatus.queued
    assert queued.updated_at == queued_at
    assert image.status is ImageStatus.uploaded
    with pytest.raises(InvalidImageStateError):
        queued.enqueue(now=queued_at)
