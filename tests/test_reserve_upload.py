from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session

from image_processor.config import DEFAULT_UPLOAD_TTL_MINUTES
from image_processor.models import ProcessingStatus
from image_processor.services.blob_storage import BlobStorage
from image_processor.services.images import reserve_upload


def test_reserve_upload_persists_a_reservation(
    session: Session,
    blob_storage: BlobStorage,
    tmp_path: Path,
) -> None:
    before = datetime.now(UTC)

    image = reserve_upload(
        session,
        blob_storage,
        filename=" cat.png ",
        content_type="image/png",
    )

    after = datetime.now(UTC)

    assert image.id is not None
    assert image.filename == "cat.png"
    assert image.content_type == "image/png"
    assert image.storage_path is not None
    stored = Path(image.storage_path)
    assert stored.name == "cat.png"
    assert stored.is_relative_to(tmp_path.resolve())
    assert not stored.exists()
    assert image.status is ProcessingStatus.awaiting_upload
    assert image.upload_token
    assert len(image.upload_token) <= 64
    expires_at = image.upload_expires_at
    assert expires_at is not None
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    ttl = timedelta(minutes=DEFAULT_UPLOAD_TTL_MINUTES)
    assert before + ttl <= expires_at <= after + ttl
    assert image.size_bytes is None
    assert image.width is None
    assert image.height is None
