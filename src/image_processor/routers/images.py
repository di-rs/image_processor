import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from .. import crud
from ..dependencies import BlobStorageDep, ImageDep, SessionDep, SettingsDep
from ..models import (
    Image,
    ImageRead,
    ImageUpdate,
    ImageUploadCreate,
    ImageUploadRead,
    ProcessingStatus,
)
from ..services import images as image_service

logger = logging.getLogger(__name__)

StatusFilter = Annotated[list[ProcessingStatus] | None, Query()]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]

router = APIRouter(prefix="/images", tags=["images"])


@router.post(
    "/uploads",
    response_model=ImageUploadRead,
    status_code=status.HTTP_201_CREATED,
)
def create_image_upload(
    payload: ImageUploadCreate,
    request: Request,
    session: SessionDep,
    storage: BlobStorageDep,
    settings: SettingsDep,
) -> ImageUploadRead:
    image = image_service.create_upload(session, payload, storage, settings)
    return ImageUploadRead(
        upload_url=str(
            request.url_for("upload_image", blob_key=image.blob_key)
        ),
    )


@router.put(
    "/uploads/{blob_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        },
    },
)
async def upload_image(blob_key: str, request: Request) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Image byte upload is not implemented",
    )


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
