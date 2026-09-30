import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .domain.images import (
    ImageDomainError,
    InvalidImageStateError,
    UploadExpiredError,
)
from .services.blob_storage import BlobStorageError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        logger.warning(
            "IntegrityError handled method=%s path=%s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Data conflict occured."},
        )

    @app.exception_handler(BlobStorageError)
    async def handle_blob_storage_error(
        request: Request, exc: BlobStorageError
    ) -> JSONResponse:
        logger.exception(
            "Blob storage failed method=%s path=%s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to delete stored file."},
        )

    @app.exception_handler(ImageDomainError)
    async def handle_image_domain_error(
        request: Request, exc: ImageDomainError
    ) -> JSONResponse:
        logger.info(
            "Domain error handled method=%s path=%s error=%s",
            request.method,
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=_domain_error_status(exc),
            content={"detail": str(exc)},
        )


def _domain_error_status(exc: ImageDomainError) -> int:
    if isinstance(exc, UploadExpiredError):
        return status.HTTP_410_GONE
    if isinstance(exc, InvalidImageStateError):
        return status.HTTP_409_CONFLICT
    return status.HTTP_422_UNPROCESSABLE_CONTENT
