from typing import Annotated

from fastapi import Depends
from pika.adapters.blocking_connection import BlockingChannel
from sqlmodel import Session

from .database import get_session
from .rabbitmq import get_channel

SessionDep = Annotated[Session, Depends(get_session)]

RabbitChannel = Annotated[
    BlockingChannel,
    Depends(get_channel),
]
