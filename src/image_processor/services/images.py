from datetime import timedelta

from sqlmodel import Session

from .. import crud
from ..config import get_settings
from ..domain.images import PreuploadedImage
from ..models import Image, ProcessingStatus
from .blob_storage import BlobStorage


def reserve_upload(
    session: Session,
    blob_storage: BlobStorage,
    *,
    filename: str,
    content_type: str,
) -> Image:
    reservation = PreuploadedImage.create(
        filename=filename,
        content_type=content_type,
        storage_path=blob_storage.reserve_path(filename),
        ttl=timedelta(minutes=get_settings().upload_ttl_minutes),
    )
    image = Image(
        filename=reservation.filename,
        content_type=reservation.content_type,
        storage_path=reservation.storage_path,
        status=ProcessingStatus.awaiting_upload,
        upload_token=reservation.upload_token,
        upload_expires_at=reservation.upload_expires_at,
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    return image


def delete_image(
    session: Session,
    image: Image,
    blob_storage: BlobStorage,
) -> None:
    blob_storage.delete(image.storage_path)
    crud.delete_image(session, image)
