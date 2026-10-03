from typing import Annotated

from dramatiq import Broker
from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from . import crud
from .broker import get_broker
from .config import Settings, get_settings
from .database import get_session
from .models import Image
from .services.blob_storage import BlobStorage, get_blob_storage

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


BlobStorageDep = Annotated[BlobStorage, Depends(get_blob_storage)]
BrokerDep = Annotated[Broker, Depends(get_broker)]


def get_image_or_404(image_id: int, session: SessionDep) -> Image:
    image = crud.get_image(session, image_id)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found.",
        )
    return image


ImageDep = Annotated[Image, Depends(get_image_or_404)]
