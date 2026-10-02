from collections.abc import Callable, Sequence
from pathlib import Path

from PIL import Image as PillowImage
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from .. import crud
from ..domain.images import ImageStatus, UploadedImage
from ..models import Image, ProcessingStatus
from .blob_storage import BlobStorage
from .images import get_original_path

ImageProcessor = Callable[[Image, Path], None]


def extract_dimensions(image: Image, original_path: Path) -> None:
    with PillowImage.open(original_path) as original:
        image.width, image.height = original.size


DEFAULT_PROCESSORS: tuple[ImageProcessor, ...] = (extract_dimensions,)


def process_image(
    session: Session,
    image: Image,
    blob_storage: BlobStorage,
    processors: Sequence[ImageProcessor] = DEFAULT_PROCESSORS,
) -> None:
    uploaded_image = UploadedImage(
        filename=image.filename,
        content_type=image.content_type,
        size_bytes=image.size_bytes,
        status=ImageStatus(image.status),
    )
    processing = uploaded_image.start_processing()

    image.status = ProcessingStatus(processing.status)
    crud.save_image(session, image)

    try:
        original_path = get_original_path(image, blob_storage)
        for processor in processors:
            processor(image, original_path)
    except SQLAlchemyError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        image.status = ProcessingStatus(processing.fail_processing().status)
        crud.save_image(session, image)
        raise

    image.status = ProcessingStatus(processing.finish_processing().status)
    crud.save_image(session, image)
