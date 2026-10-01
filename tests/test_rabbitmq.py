import json
from unittest.mock import MagicMock

from pika.adapters.blocking_connection import BlockingChannel

from image_processor.rabbitmq import IMAGE_PROCESSING_QUEUE, RabbitMQClient


def test_publish_image() -> None:
    channel = MagicMock(spec=BlockingChannel)
    client = RabbitMQClient(channel)

    client.publish_image(42)

    channel.queue_declare.assert_called_once_with(
        queue=IMAGE_PROCESSING_QUEUE, durable=True
    )
    channel.confirm_delivery.assert_called_once_with()
    channel.basic_publish.assert_called_once()
    kwargs = channel.basic_publish.call_args.kwargs
    assert kwargs["exchange"] == ""
    assert kwargs["routing_key"] == IMAGE_PROCESSING_QUEUE
    assert json.loads(kwargs["body"]) == {"image_id": 42}
    assert kwargs["properties"].delivery_mode == 2
    assert kwargs["properties"].content_type == "application/json"
    assert kwargs["mandatory"] is True
