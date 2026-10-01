from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from image_processor.config import get_settings
from image_processor.database import get_engine, get_session
from image_processor.domain.blob_key import BlobKey
from image_processor.main import app
from image_processor.rabbitmq import (
    RabbitMQClient,
    get_connection_parameters,
    get_rabbitmq_client,
)
from image_processor.services.blob_storage import BlobStorage, get_blob_storage


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="rabbitmq")
def rabbitmq_fixture() -> MagicMock:
    return MagicMock(spec=RabbitMQClient)


@pytest.fixture(name="blob_storage")
def blob_storage_fixture() -> BlobStorage:
    storage = MagicMock(spec=BlobStorage)
    storage.create_key.return_value = BlobKey("test-blob-key")
    return storage


@pytest.fixture(name="client")
def client_fixture(
    session: Session,
    rabbitmq: MagicMock,
    blob_storage: BlobStorage,
) -> Generator[TestClient]:
    def get_session_override() -> Generator[Session]:
        yield session

    def get_rabbitmq_client_override() -> RabbitMQClient:
        return rabbitmq

    def get_blob_storage_override() -> BlobStorage:
        return blob_storage

    app.dependency_overrides[get_blob_storage] = get_blob_storage_override
    app.dependency_overrides[get_session] = get_session_override

    app.dependency_overrides[get_rabbitmq_client] = get_rabbitmq_client_override
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_blob_storage.cache_clear()
        get_connection_parameters.cache_clear()
