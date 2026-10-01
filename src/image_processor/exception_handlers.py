import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .domain.images import (
    ImageDomainError,
    InvalidImageStateError,
)


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

    if isinstance(exc, InvalidImageStateError):
        return status.HTTP_409_CONFLICT
    return status.HTTP_422_UNPROCESSABLE_CONTENT
