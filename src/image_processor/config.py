import logging
from functools import lru_cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://image_processor:image_processor@localhost:5432/image_processor"
DEFAULT_RABBITMQ_URL = "amqp://image_processor:image_processor@localhost:5672"
DEFAULT_STORAGE_DIR = "/data/images"
DEFAULT_UPLOAD_TTL_MINUTES = 15
DEFAULT_UPLOAD_TOKEN_SECRET = "image-processor-upload-token"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class Settings(BaseSettings):
    database_url: str = DEFAULT_DATABASE_URL
    rabbitmq_url: str = DEFAULT_RABBITMQ_URL
    storage_dir: str = DEFAULT_STORAGE_DIR
    upload_ttl_minutes: PositiveInt = DEFAULT_UPLOAD_TTL_MINUTES
    upload_token_secret: str = DEFAULT_UPLOAD_TOKEN_SECRET
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8"
    )


def configure_logging(*, debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
