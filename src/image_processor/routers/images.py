import logging
from typing import Annotated

from fastapi import APIRouter, Query, status

from .. import crud
from ..dependencies import ImageDep, SessionDep
from ..models import (
    Image,
    ImageRead,
    ImageUpdate,
    ProcessingStatus,
)


logger = logging.getLogger(__name__)

StatusFilter = Annotated[list[ProcessingStatus] | None, Query()]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]

router = APIRouter(prefix="/images", tags=["images"])


@router.get("", response_model=list[ImageRead])
def list_images(
    session: SessionDep,
    status: StatusFilter = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[Image]:
    logger.info(
        "Listing images status=%s limit=%s offset=%s",
        status,
        limit,
        offset,
    )
    return crud.list_images(
        session,
        statuses=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{image_id}", response_model=ImageRead)
def read_image(image: ImageDep) -> Image:
    logger.info("Reading image image_id=%s", image.id)
    return image


@router.patch("/{image_id}", response_model=ImageRead)
def update_image(
    image: ImageDep,
    payload: ImageUpdate,
    session: SessionDep,
) -> Image:
    logger.info("Updating image image_id=%s", image.id)
    return crud.update_image(session, image, payload)


@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_image(
    image: ImageDep,
    session: SessionDep,
) -> None:
    logger.info("Deleting image image_id=%s", image.id)
    crud.delete_image(session, image)
