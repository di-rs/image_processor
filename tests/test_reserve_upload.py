from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from image_processor.config import DEFAULT_UPLOAD_TTL_MINUTES
from image_processor.services.blob_storage import BlobStorage
from image_processor.services.images import reserve_upload


def test_reserve_upload_persists_a_reservation(
    session: Session,
    blob_storage: BlobStorage,
) -> None:
    before = datetime.now(UTC)

    reservation = reserve_upload(
        session,
        blob_storage,
        filename=" cat.png ",
        content_type="image/png",
    )

    after = datetime.now(UTC)
    token = reservation.upload_url.removeprefix("/images/uploads/")

    assert reservation.id == 1
    assert token
    assert reservation.upload_url == f"/images/uploads/{token}"
    expires_at = reservation.upload_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    ttl = timedelta(minutes=DEFAULT_UPLOAD_TTL_MINUTES)
    assert before + ttl <= expires_at <= after + ttl
