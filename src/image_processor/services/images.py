from datetime import timedelta

from sqlmodel import Session

from .. import crud
from ..config import Settings
from ..domain.images import PendingImageUpload
from ..models import Image, ImageUploadCreate, utc_now
from .blob_storage import BlobStorage


def create_upload(
    session: Session,
    payload: ImageUploadCreate,
    blob_storage: BlobStorage,
    settings: Settings,
) -> Image:
    upload_expires_at = utc_now() + timedelta(
        seconds=settings.upload_url_ttl_seconds
    )
    pending = PendingImageUpload.create(
        filename=payload.filename,
        size_bytes=payload.size_bytes,
        blob_key=str(blob_storage.create_key()),
        upload_expires_at=upload_expires_at,
    )
    return crud.create_upload(session, pending)
