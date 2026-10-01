from collections.abc import AsyncIterable
from datetime import timedelta
from pathlib import Path

from sqlmodel import Session

from .. import crud
from ..config import Settings
from ..domain.blob_key import BlobKey
from ..domain.images import (
    ImageNotFoundError,
    InvalidImageStateError,
    PendingImageUpload,
    UploadExpiredError,
)
from ..models import (
    Image,
    ImageUploadCreate,
    ProcessingStatus,
    utc_now,
)
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


def claim_upload(session: Session, blob_key: BlobKey) -> Image:
    image = crud.claim_upload(session, blob_key)
    if image is not None:
        return image

    image = crud.get_image_by_blob_key(session, blob_key)
    if image is None:
        raise ImageNotFoundError("Upload not found")
    if image.status == ProcessingStatus.pending_upload:
        crud.delete_image(session, image)
        raise UploadExpiredError("Upload URL has expired")
    raise InvalidImageStateError("Upload URL has already been used")


def get_original_path(image: Image, blob_storage: BlobStorage) -> Path:
    if image.blob_key is None or image.status in {
        ProcessingStatus.pending_upload,
        ProcessingStatus.uploading,
    }:
        raise ImageNotFoundError("Image bytes not available")
    return blob_storage.get_image_path(BlobKey(image.blob_key))


def delete_image(
    session: Session, image: Image, blob_storage: BlobStorage
) -> None:
    if image.status == ProcessingStatus.uploading:
        raise InvalidImageStateError("Cannot delete an active upload")
    if image.blob_key is not None:
        blob_storage.delete_image(BlobKey(image.blob_key))
    crud.delete_image(session, image)


async def upload_image(
    session: Session,
    blob_key: BlobKey,
    chunks: AsyncIterable[bytes],
    blob_storage: BlobStorage,
) -> None:
    image = claim_upload(session, blob_key)
    stored = False
    try:
        await blob_storage.create_image(blob_key, chunks, image.size_bytes)
        stored = True
        crud.complete_upload(session, image)
    except BaseException:
        try:
            if stored:
                blob_storage.delete_image(blob_key)
        finally:
            crud.discard_upload(session, image)
        raise
