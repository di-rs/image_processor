import logging
from asyncio import run
from collections.abc import AsyncIterable, Callable, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from random import Random

from PIL import Image as PillowImage
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from .. import crud
from ..config import get_settings
from ..domain.blob_key import BlobKey
from ..domain.images import ImageStatus, UploadedImage
from ..models import (
    MAX_FILENAME_LENGTH,
    Image,
    ImageUploadCreate,
    ProcessingStatus,
)
from .blob_storage import BlobStorage
from .images import create_upload, get_original_path, upload_image

logger = logging.getLogger(__name__)
RETRYABLE_FAILURE = "processing.retryable_failure"


@dataclass
class ProcessingContext:
    session: Session
    image: Image
    original: PillowImage.Image
    blob_storage: BlobStorage
    generated_image: Image | None = None


ImageProcessor = Callable[[ProcessingContext], None]


def extract_dimensions(context: ProcessingContext) -> None:
    context.image.width, context.image.height = context.original.size


def shuffle_pixels(context: ProcessingContext) -> None:
    mode = context.original.mode
    if mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "I", "I;16"}:
        mode = "RGBA" if context.original.has_transparency_data else "RGB"
    with context.original.convert(mode) as shuffled:
        pixels = list(shuffled.get_flattened_data())
        Random().shuffle(pixels)
        shuffled.putdata(pixels)
        with BytesIO() as output:
            shuffled.save(output, format="PNG")
            data = output.getvalue()

    async def chunks() -> AsyncIterable[bytes]:
        yield data

    suffix = "-shuffled.png"
    stem = Path(context.image.filename).stem
    filename = f"{stem[: MAX_FILENAME_LENGTH - len(suffix)]}{suffix}"
    generated = create_upload(
        context.session,
        ImageUploadCreate(filename=filename, size_bytes=len(data)),
        context.blob_storage,
        get_settings(),
    )
    context.generated_image = generated
    if generated.blob_key is None:
        raise ValueError("Generated image has no blob key")
    generated = run(
        upload_image(
            context.session,
            BlobKey(generated.blob_key),
            chunks(),
            context.blob_storage,
        )
    )
    generated.original_image = context.image.id
    generated.width = context.image.width
    generated.height = context.image.height
    generated.status = ProcessingStatus.finished
    context.session.add(generated)


DEFAULT_PROCESSORS: tuple[ImageProcessor, ...] = (
    extract_dimensions,
    shuffle_pixels,
)


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

    crud.update_image_status(session, image, processing)

    log_id = str(image.id)
    extra = {"image_id": log_id, "event_name": "processing.started"}
    logger.info("Processing started", extra=extra)
    context: ProcessingContext | None = None
    try:
        original_path = get_original_path(image, blob_storage)
        with PillowImage.open(original_path) as original:
            context = ProcessingContext(session, image, original, blob_storage)
            for processor in processors:
                processor(context)

        finished = processing.finish_processing()
        crud.update_image_status(session, image, finished)
        extra = {"image_id": log_id, "event_name": "processing.finished"}
        logger.info("Processing finished", extra=extra)
    except Exception as exc:
        if isinstance(exc, SQLAlchemyError):
            extra = {"image_id": log_id, "event_name": RETRYABLE_FAILURE}
            logger.error("DB failure: %s", type(exc).__name__, extra=extra)
        else:
            extra = {"image_id": log_id, "event_name": "processing.failed"}
            logger.exception("Processing failed", extra=extra)
        session.rollback()
        if context is not None and context.generated_image is not None:
            generated = context.generated_image
            if generated.blob_key is not None:
                blob_storage.delete_image(generated.blob_key)
            crud.discard_upload(session, generated)
        if not isinstance(exc, SQLAlchemyError):
            failed = processing.fail_processing()
            crud.update_image_status(session, image, failed)
        raise
