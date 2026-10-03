import logging
from typing import Annotated

import dramatiq
from pydantic import Field, validate_call
from sqlalchemy.exc import SQLAlchemyError

from .. import crud
from ..broker import IMAGE_PROCESSING_QUEUE, get_broker
from ..config import get_settings
from ..database import open_session
from ..models import ProcessingStatus
from ..services.blob_storage import get_blob_storage
from ..services.image_processing import process_image

logger = logging.getLogger(__name__)


def retry_database_failure(retries: int, exception: BaseException) -> bool:
    return isinstance(exception, SQLAlchemyError)


@dramatiq.actor(
    broker=get_broker(),
    queue_name=IMAGE_PROCESSING_QUEUE,
    max_retries=None,
    retry_when=retry_database_failure,
    min_backoff=get_settings().worker_failure_backoff_seconds * 1000,
    max_backoff=get_settings().worker_failure_backoff_seconds * 1000,
)
@validate_call
def process_message(image_id: Annotated[int, Field(gt=0, strict=True)]) -> None:
    with open_session() as session:
        image = crud.get_image(session, image_id)
        if image is None or image.status == ProcessingStatus.finished:
            logger.info("Skipping image: image_id=%s", image_id)
            return
        process_image(session, image, get_blob_storage())
    logger.info("Image processing completed: image_id=%s", image_id)
