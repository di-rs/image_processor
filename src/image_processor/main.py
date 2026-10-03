import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request

from . import __version__
from .app.exception_handlers import register_exception_handlers
from .broker import IMAGE_PROCESSING_QUEUE, get_broker
from .config import configure_logging, get_settings
from .database import dispose_engine
from .routers import images

APP_NAME = "Image Processing API"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging(debug=get_settings().debug)
    broker = get_broker()
    try:
        await asyncio.to_thread(
            broker.declare_queue, IMAGE_PROCESSING_QUEUE, ensure=True
        )
        yield
    finally:
        try:
            await asyncio.to_thread(broker.close)
        finally:
            await asyncio.to_thread(dispose_engine)


app = FastAPI(
    title=APP_NAME,
    version=__version__,
    description="Image Processing API with queue and processing workers.",
    lifespan=lifespan,
)
register_exception_handlers(app)


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def read_root() -> dict[str, str]:
    logger.debug("Serving root metadata")
    return {
        "app": APP_NAME,
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
