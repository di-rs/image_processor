from sqlmodel import Session

from .. import crud
from ..domain.images import UploadedImage
from ..models import Image, UploadTargetRead
from .blob_storage import BlobStorage


def create_upload_target(
    blob_storage: BlobStorage,
    *,
    filename: str,
    content_type: str,
) -> UploadTargetRead:
    token = blob_storage.issue_upload_token(
        filename=filename,
        content_type=content_type,
    )
    return UploadTargetRead(upload_url=blob_storage.create_upload_url(token))


def upload_image(
    session: Session,
    blob_storage: BlobStorage,
    *,
    upload_token: str,
    data: bytes,
    width: int,
    height: int,
) -> Image:
    token = blob_storage.parse_upload_token(upload_token)
    size_bytes = blob_storage.save(token.blob_key, data)
    uploaded = UploadedImage(
        filename=token.filename,
        content_type=token.content_type,
        size_bytes=size_bytes,
        width=width,
        height=height,
    )
    return crud.create_image(session, uploaded, token.blob_key)


def delete_image(
    session: Session,
    image: Image,
    blob_storage: BlobStorage,
) -> None:
    blob_storage.delete(image.blob_key)
    crud.delete_image(session, image)
