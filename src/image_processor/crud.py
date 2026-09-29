from sqlmodel import Session, col, select

from .models import Image, ImageUpdate, ProcessingStatus
from .services import blob_storage


def list_images(
    session: Session,
    status: ProcessingStatus | None = None,
) -> list[Image]:
    statement = select(Image).order_by(col(Image.created_at).desc())
    if status is not None:
        statement = statement.where(Image.status == status)
    images = session.exec(statement).all()
    return list(images)


def get_image(session: Session, image_id: int) -> Image | None:
    image = session.get(Image, image_id)
    return image


def update_image(session: Session, image: Image, payload: ImageUpdate) -> Image:
    updated_fields = payload.model_dump(exclude_unset=True)
    image.sqlmodel_update(updated_fields)
    session.add(image)
    session.commit()
    session.refresh(image)
    return image


def delete_image(session: Session, image: Image) -> None:
    storage_path = image.storage_path
    session.delete(image)
    session.commit()
    blob_storage.delete(storage_path)
