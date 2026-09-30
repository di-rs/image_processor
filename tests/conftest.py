from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pika.adapters.blocking_connection import BlockingChannel
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from image_processor.config import get_settings
from image_processor.database import get_engine, get_session
from image_processor.main import app
from image_processor.rabbitmq import get_channel, get_connection_parameters
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


@pytest.fixture(name="blob_storage")
def blob_storage_fixture(tmp_path: Path) -> BlobStorage:
    return BlobStorage(tmp_path)


@pytest.fixture(name="channel")
def channel_fixture() -> BlockingChannel:
    return MagicMock(spec=BlockingChannel)


@pytest.fixture(name="client")
def client_fixture(
    session: Session,
    blob_storage: BlobStorage,
    channel: BlockingChannel,
) -> Generator[TestClient]:
    def get_session_override() -> Generator[Session]:
        yield session

    def get_channel_override() -> Generator[BlockingChannel]:
        yield channel

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_blob_storage] = lambda: blob_storage
    app.dependency_overrides[get_channel] = get_channel_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_blob_storage.cache_clear()
    get_connection_parameters.cache_clear()
