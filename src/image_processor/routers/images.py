import logging
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import FileResponse

from .. import crud
from ..dependencies import (
    BlobStorageDep,
    BrokerDep,
    ImageDep,
    SessionDep,
    SettingsDep,
)
from ..domain.blob_key import BlobKey
from ..models import (
    ImageRead,
    ImageUpdate,
    ImageUploadCreate,
    ImageUploadRead,
    ProcessingStatus,
)
from ..services import images as image_service
from ..workers.image_processing import process_message

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
async def upload_image(
    blob_key: str,
    request: Request,
    session: SessionDep,
    storage: BlobStorageDep,
    broker: BrokerDep,
) -> None:
    image = await image_service.upload_image(
        session, BlobKey(blob_key), request.stream(), storage
    )
    broker.enqueue(process_message.message(image.id))
    crud.mark_image_queued(session, image.id)


@router.get("/{image_id}/original", response_class=FileResponse)
def read_original(image: ImageDep, storage: BlobStorageDep) -> FileResponse:
    path = image_service.get_original_path(image, storage)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=image.filename,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("", response_model=list[ImageRead])
def list_images(
    session: SessionDep,
    request: Request,
    status: StatusFilter = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[ImageRead]:
    logger.info(
        "Listing images status=%s limit=%s offset=%s",
        status,
        limit,
        offset,
    )
    images = crud.list_images(
        session,
        statuses=status,
        limit=limit,
        offset=offset,
    )
    return [
        ImageRead.from_image(
            image,
            original_url=str(
                request.url_for("read_original", image_id=image.id)
            ),
        )
        for image in images
    ]


@router.get("/{image_id}", response_model=ImageRead)
def read_image(
    image: ImageDep,
    session: SessionDep,
    request: Request,
    include_generated: bool = False,
) -> ImageRead:
    logger.info("Reading image image_id=%s", image.id)
    generated = image_service.get_generated_images(
        session, image.id, include_generated=include_generated
    )
    return ImageRead.from_image(
        image,
        original_url=str(request.url_for("read_original", image_id=image.id)),
        generated_images=[
            ImageRead.from_image(
                child,
                original_url=str(
                    request.url_for("read_original", image_id=child.id)
                ),
            )
            for child in generated
        ],
    )


@router.patch("/{image_id}", response_model=ImageRead)
def update_image(
    image: ImageDep,
    payload: ImageUpdate,
    session: SessionDep,
    request: Request,
) -> ImageRead:
    logger.info("Updating image image_id=%s", image.id)
    updated = crud.update_image(session, image, payload)
    return ImageRead.from_image(
        updated,
        original_url=str(request.url_for("read_original", image_id=updated.id)),
    )


@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_image(
    image: ImageDep,
    session: SessionDep,
    storage: BlobStorageDep,
) -> None:
    logger.info("Deleting image image_id=%s", image.id)
    image_service.delete_image(session, image, storage)
