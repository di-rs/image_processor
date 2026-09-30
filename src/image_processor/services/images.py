from datetime import timedelta

from sqlmodel import Session

from .. import crud
from ..config import get_settings
from ..domain.images import PreuploadedImage
from ..models import Image, UploadReservationRead
from .blob_storage import BlobStorage


def reserve_upload(
    session: Session,
    blob_storage: BlobStorage,
    *,
    filename: str,
    content_type: str,
) -> UploadReservationRead:
    reservation = PreuploadedImage.create(
        filename=filename,
        content_type=content_type,
        ttl=timedelta(minutes=get_settings().upload_ttl_minutes),
    )
    image = crud.create_image(session, reservation)
    return UploadReservationRead(
        id=image.id,
        upload_url=blob_storage.create_upload_url(reservation.upload_token),
        upload_expires_at=reservation.upload_expires_at,
    )


def delete_image(
    session: Session,
    image: Image,
    blob_storage: BlobStorage,
) -> None:
    blob_storage.delete(image.blob_key)
    crud.delete_image(session, image)
