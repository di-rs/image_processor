from collections.abc import Generator
from functools import lru_cache

import pika
from pika.adapters.blocking_connection import BlockingChannel

from .config import get_settings


@lru_cache
def get_connection_parameters() -> pika.URLParameters:
    return pika.URLParameters(get_settings().rabbitmq_url)


def get_channel() -> Generator[BlockingChannel, None, None]:
    connection = pika.BlockingConnection(get_connection_parameters())

    channel = connection.channel()

    try:
        yield channel
    finally:
        if channel.is_open:
            channel.close()

        if connection.is_open:
            connection.close()
