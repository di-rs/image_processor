from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import dramatiq
from dramatiq import Broker
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.middleware import Middleware, Retries
from dramatiq.worker import Worker

from .config import configure_logging, get_settings
from .database import dispose_engine

IMAGE_PROCESSING_QUEUE = "image_processing_tasks"


class WorkerResources(Middleware):
    def after_process_boot(self, broker: Broker) -> None:
        configure_logging(
            settings=get_settings(), service_name="image-processor-worker"
        )

    def after_worker_shutdown(self, broker: Broker, worker: Worker) -> None:
        dispose_engine()


@lru_cache
def get_broker() -> RabbitmqBroker:
    settings = get_settings()
    url = urlsplit(settings.rabbitmq_url)
    parameters = dict(parse_qsl(url.query))
    parameters.update(
        socket_timeout=str(settings.rabbitmq_connection_timeout_seconds),
        stack_timeout=str(settings.rabbitmq_connection_timeout_seconds),
        blocked_connection_timeout=str(
            settings.rabbitmq_blocked_connection_timeout_seconds
        ),
    )
    broker = RabbitmqBroker(
        url=urlunsplit(url._replace(query=urlencode(parameters))),
        confirm_delivery=True,
        middleware=[Retries(), WorkerResources()],
    )
    dramatiq.set_broker(broker)
    return broker
