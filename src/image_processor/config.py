import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://image_processor:image_processor@localhost:5432/image_processor"
DEFAULT_RABBITMQ_URL = "amqp://image_processor:image_processor@localhost:5672"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class Settings(BaseSettings):
    database_url: str = DEFAULT_DATABASE_URL
    rabbitmq_url: str = DEFAULT_RABBITMQ_URL
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
