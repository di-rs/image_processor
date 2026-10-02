from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache

import pika
from fastapi import Depends
from pika.adapters.blocking_connection import BlockingChannel
from pydantic import BaseModel, Field

from .config import get_settings


@lru_cache
def get_connection_parameters() -> pika.URLParameters:
    return pika.URLParameters(get_settings().rabbitmq_url)


IMAGE_PROCESSING_QUEUE = "image_processing"


class ImageProcessingMessage(BaseModel):
    image_id: int = Field(gt=0, strict=True)


@dataclass
class RabbitMQClient:
    _channel: BlockingChannel

    def publish_image(self, image_id: int) -> None:
        self._channel.queue_declare(queue=IMAGE_PROCESSING_QUEUE, durable=True)
        self._channel.confirm_delivery()
        self._channel.basic_publish(
            exchange="",
            routing_key=IMAGE_PROCESSING_QUEUE,
            body=ImageProcessingMessage(image_id=image_id)
            .model_dump_json()
            .encode(),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
            mandatory=True,
        )


@contextmanager
def open_channel() -> Generator[BlockingChannel, None, None]:
    connection = pika.BlockingConnection(get_connection_parameters())

    try:
        channel = connection.channel()
        try:
            yield channel
        finally:
            if channel.is_open:
                channel.close()
    finally:
        if connection.is_open:
            connection.close()


def get_channel() -> Generator[BlockingChannel, None, None]:
    with open_channel() as channel:
        yield channel


def get_rabbitmq_client(
    channel: BlockingChannel = Depends(get_channel),
) -> RabbitMQClient:
    return RabbitMQClient(channel)
