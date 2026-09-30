from sqlmodel import Session

from .. import crud
from ..models import Image
from .blob_storage import BlobStorage


def delete_image(
    session: Session,
    image: Image,
    blob_storage: BlobStorage,
) -> None:
    blob_storage.delete(image.storage_path)
    crud.delete_image(session, image)
