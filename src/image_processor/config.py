import logging
from functools import lru_cache
from pathlib import Path

from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://image_processor:image_processor@localhost:5432/image_processor"
DEFAULT_RABBITMQ_URL = "amqp://image_processor:image_processor@localhost:5672"
DEFAULT_UPLOAD_URL_TTL_SECONDS = 300
DEFAULT_BLOB_STORAGE_PATH = Path("./data/images")


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class Settings(BaseSettings):
    database_url: str = DEFAULT_DATABASE_URL
    rabbitmq_url: str = DEFAULT_RABBITMQ_URL
    rabbitmq_connection_timeout_seconds: PositiveInt = 10
    rabbitmq_blocked_connection_timeout_seconds: PositiveInt = 10

    worker_failure_backoff_seconds: PositiveInt = 5

    upload_url_ttl_seconds: PositiveInt = DEFAULT_UPLOAD_URL_TTL_SECONDS
    blob_storage_path: Path = DEFAULT_BLOB_STORAGE_PATH

    debug: bool = False
    telemetry_enabled: bool = False
    otel_logs_endpoint: str = Field(
        default="http://127.0.0.1:4318/v1/logs",
        validation_alias="OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


def configure_logging(*, settings: Settings, service_name: str) -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT)
    root = logging.getLogger()
    root.setLevel(level)
    if not settings.telemetry_enabled or any(
        isinstance(handler, LoggingHandler) for handler in root.handlers
    ):
        return
    # Standard OTEL_RESOURCE_ATTRIBUTES can override the default namespace.
    resource = Resource({"service.namespace": "image-processor"}).merge(
        Resource.create({"service.name": service_name})
    )
    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(endpoint=settings.otel_logs_endpoint)
        )
    )
    handler = LoggingHandler(logger_provider=provider)
    handler.addFilter(logging.Filter("image_processor"))
    root.addHandler(handler)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
