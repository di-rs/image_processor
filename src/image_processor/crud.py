from sqlmodel import Session, col, select

from .domain.images import UploadedImage
from .models import Image, ImageUpdate, ProcessingStatus


def list_images(
    session: Session,
    *,
    statuses: list[ProcessingStatus] | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[Image]:
    statement = select(Image).order_by(col(Image.created_at).desc())
    if statuses:
        statement = statement.where(col(Image.status).in_(statuses))
    if offset is not None:
        statement = statement.offset(offset)
    if limit is not None:
        statement = statement.limit(limit)
    images = session.exec(statement).all()
    return list(images)


def get_image(session: Session, image_id: int) -> Image | None:
    image = session.get(Image, image_id)
    return image


def create_image(
    session: Session,
    uploaded: UploadedImage,
    blob_key: str,
) -> Image:
    image = Image(
        filename=uploaded.filename,
        content_type=uploaded.content_type,
        blob_key=blob_key,
        status=ProcessingStatus(uploaded.status),
        size_bytes=uploaded.size_bytes,
        width=uploaded.width,
        height=uploaded.height,
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    return image


def update_image(session: Session, image: Image, payload: ImageUpdate) -> Image:
    updated_fields = payload.model_dump(exclude_unset=True)
    image.sqlmodel_update(updated_fields)
    session.add(image)
    session.commit()
    session.refresh(image)
    return image


def delete_image(session: Session, image: Image) -> None:
    session.delete(image)
    session.commit()
