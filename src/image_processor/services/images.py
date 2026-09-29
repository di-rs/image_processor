from sqlmodel import Session

from .. import crud
from ..models import Image
from .blob_storage import delete as delete_blob


def delete_image(session: Session, image: Image) -> None:
    delete_blob(image.storage_path)
    crud.delete_image(session, image)
