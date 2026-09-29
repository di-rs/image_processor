import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from . import __version__
from .config import configure_logging, get_settings
from .routers import images

APP_NAME = "Image Processing API"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging(debug=get_settings().debug)
    yield


app = FastAPI(
    title=APP_NAME,
    version=__version__,
    description="Image Processing API with queue and processing workers.",
    lifespan=lifespan,
)


@app.exception_handler(IntegrityError)
def handle_integrity_error(
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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000

    logger.info(
        "%s %s completed in %.2fms with status code %s",
        request.method,
        request.url.path,
        process_time,
        response.status_code,
    )
    return response


app.include_router(images.router)


@app.get("/")
def read_root() -> dict[str, str]:
    logger.debug("Serving root metadata")
    return {
        "app": APP_NAME,
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
