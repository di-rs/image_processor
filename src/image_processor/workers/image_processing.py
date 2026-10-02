import logging
import signal

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic
from sqlalchemy.exc import SQLAlchemyError

from .. import crud
from ..config import configure_logging, get_settings
from ..database import get_engine, open_session
from ..rabbitmq import (
    IMAGE_PROCESSING_QUEUE,
    ImageProcessingMessage,
    open_channel,
)
from ..services.blob_storage import get_blob_storage
from ..services.image_processing import process_image

logger = logging.getLogger(__name__)


def process_message(body: bytes) -> None:
    message = ImageProcessingMessage.model_validate_json(body)
    with open_session() as session:
        image = crud.get_image(session, message.image_id)
        if image is None:
            logger.info("Skipping missing image: image_id=%s", message.image_id)
            return
        process_image(session, image, get_blob_storage())
    logger.info("Image processing completed: image_id=%s", message.image_id)


def handle_message(
    channel: BlockingChannel,
    method: Basic.Deliver,
    properties: pika.BasicProperties,
    body: bytes,
) -> None:
    try:
        process_message(body)
    except SQLAlchemyError:
        # Closing the connection requeues the unacknowledged delivery.
        logger.exception("Database failure while processing image message")
        raise
    except Exception:
        logger.exception("Image message processing failed")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    else:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def run_consumer(channel: BlockingChannel) -> None:
    channel.queue_declare(queue=IMAGE_PROCESSING_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=IMAGE_PROCESSING_QUEUE,
        on_message_callback=handle_message,
        auto_ack=False,
    )
    previous_handler = signal.getsignal(signal.SIGTERM)

    def stop(signum: int, frame: object) -> None:
        channel.connection.add_callback_threadsafe(channel.stop_consuming)

    signal.signal(signal.SIGTERM, stop)
    try:
        logger.info("Waiting for image processing messages")
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


def main() -> None:
    configure_logging(debug=get_settings().debug)
    try:
        with open_channel() as channel:
            run_consumer(channel)
    finally:
        get_engine().dispose()


if __name__ == "__main__":
    main()
