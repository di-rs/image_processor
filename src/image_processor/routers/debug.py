from typing import Annotated, Literal, cast

from fastapi import APIRouter, Query, Request
from sqlalchemy import case, func
from sqlmodel import col, select

from ..broker import IMAGE_PROCESSING_QUEUE
from ..dependencies import ImageDep, SessionDep
from ..models import (
    DebugImagePage,
    DebugImageRead,
    DebugSummary,
    Image,
    ProcessingStatus,
)

router = APIRouter(prefix="/debug", tags=["debug"])

StatusFilter = Annotated[list[ProcessingStatus] | None, Query()]
Kind = Literal["all", "original", "generated"]
Order = Literal["newest", "oldest", "queue"]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def _debug_image(image: Image, request: Request) -> DebugImageRead:
    return cast(
        DebugImageRead,
        DebugImageRead.from_image(
            image,
            original_url=str(
                request.url_for("read_original", image_id=image.id)
            ),
        ),
    )


@router.get("/images", response_model=DebugImagePage)
def list_debug_images(
    session: SessionDep,
    request: Request,
    status: StatusFilter = None,
    kind: Kind = "all",
    order: Order = "newest",
    limit: Limit = 20,
    offset: Offset = 0,
) -> DebugImagePage:
    """List local debug metadata; this endpoint has no authentication.

    Kind reflects the current original_image link: original means NULL,
    generated means non-NULL. Deleting a parent clears the link, so orphaned
    children appear as originals; historical lineage is not retained.

    Queue order is DB state, not broker position: processing, queued,
    awaiting upload/publication (uploaded/uploading/pending_upload), then
    terminal records. Each group is oldest-first, with ID breaking age ties.
    """
    statement = select(Image)
    if status:
        statement = statement.where(col(Image.status).in_(status))
    if kind == "original":
        statement = statement.where(col(Image.original_image).is_(None))
    elif kind == "generated":
        statement = statement.where(col(Image.original_image).is_not(None))

    total = session.exec(
        select(func.count()).select_from(statement.subquery())
    ).one()
    if order == "newest":
        statement = statement.order_by(
            col(Image.created_at).desc(), col(Image.id).desc()
        )
    else:
        if order == "queue":
            priority = case(
                (col(Image.status) == ProcessingStatus.processing, 0),
                (col(Image.status) == ProcessingStatus.queued, 1),
                (
                    col(Image.status).in_(
                        [
                            ProcessingStatus.uploaded,
                            ProcessingStatus.uploading,
                            ProcessingStatus.pending_upload,
                        ]
                    ),
                    2,
                ),
                else_=3,
            )
            statement = statement.order_by(priority)
        statement = statement.order_by(
            col(Image.created_at).asc(), col(Image.id).asc()
        )

    images = session.exec(statement.limit(limit).offset(offset)).all()
    return DebugImagePage(
        items=[_debug_image(image, request) for image in images],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=DebugSummary)
def read_debug_summary(session: SessionDep) -> DebugSummary:
    """Count image records, including generated children, not broker jobs."""
    counts = dict.fromkeys(ProcessingStatus, 0)
    for status, count in session.exec(
        select(Image.status, func.count()).group_by(Image.status)
    ).all():
        counts[ProcessingStatus(status)] = count
    return DebugSummary(
        counts=counts,
        total=sum(counts.values()),
        queue_name=IMAGE_PROCESSING_QUEUE,
    )


@router.get("/images/{image_id}", response_model=DebugImageRead)
def read_debug_image(image: ImageDep, request: Request) -> DebugImageRead:
    """Read local debug metadata without fetching generated children."""
    return _debug_image(image, request)
