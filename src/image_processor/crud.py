from sqlalchemy import update
from sqlmodel import Session, col, select

from .domain.blob_key import BlobKey
from .domain.images import (
    PendingImageUpload,
    UploadedImage,
)
from .models import Image, ImageUpdate, ProcessingStatus, utc_now


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
) -> Image:
    image = Image(
        filename=uploaded.filename,
        content_type=uploaded.content_type,
        status=ProcessingStatus(uploaded.status),
        size_bytes=uploaded.size_bytes,
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    return image


def create_upload(session: Session, pending: PendingImageUpload) -> Image:
    image = Image(
        filename=pending.filename,
        content_type=pending.content_type,
        size_bytes=pending.size_bytes,
        status=ProcessingStatus(pending.status),
        blob_key=pending.blob_key,
        upload_expires_at=pending.upload_expires_at,
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    return image


def claim_upload(session: Session, blob_key: BlobKey) -> Image | None:
    statement = (
        update(Image)
        .where(
            col(Image.blob_key) == str(blob_key),
            col(Image.status) == ProcessingStatus.pending_upload,
            col(Image.upload_expires_at) > utc_now(),
        )
        .values(status=ProcessingStatus.uploading)
        .returning(Image)
        .execution_options(synchronize_session=False)
    )
    image = session.execute(statement).scalar_one_or_none()
    session.commit()
    return image


def get_image_by_blob_key(session: Session, blob_key: BlobKey) -> Image | None:
    return session.exec(
        select(Image).where(col(Image.blob_key) == str(blob_key))
    ).first()


def save_image(session: Session, image: Image) -> None:
    session.add(image)
    session.commit()


def discard_upload(session: Session, image: Image) -> None:
    session.rollback()
    stored_image = session.get(Image, image.id)
    if stored_image is not None:
        delete_image(session, stored_image)


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
