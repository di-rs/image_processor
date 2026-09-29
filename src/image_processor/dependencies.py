from typing import Annotated

from fastapi import Depends, HTTPException, status
from pika.adapters.blocking_connection import BlockingChannel
from sqlmodel import Session

from . import crud
from .database import get_session
from .models import Image
from .rabbitmq import get_channel

SessionDep = Annotated[Session, Depends(get_session)]

RabbitChannel = Annotated[
    BlockingChannel,
    Depends(get_channel),
]


def get_image_or_404(image_id: int, session: SessionDep) -> Image:
    image = crud.get_image(session, image_id)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found.",
        )
    return image


ImageDep = Annotated[Image, Depends(get_image_or_404)]
