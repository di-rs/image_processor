from collections.abc import Callable, Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from image_processor.broker import get_broker
from image_processor.config import get_settings
from image_processor.database import get_engine, get_session
from image_processor.main import app
from image_processor.models import Image, ProcessingStatus
from image_processor.services.blob_storage import BlobStorage, get_blob_storage


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture(name="broker")
def broker_fixture() -> MagicMock:
    return MagicMock(spec=RabbitmqBroker)


@pytest.fixture(name="blob_storage")
def blob_storage_fixture(tmp_path: Path) -> BlobStorage:
    return BlobStorage(tmp_path)


@pytest.fixture(name="client")
def client_fixture(
    session: Session,
    broker: MagicMock,
    blob_storage: BlobStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient]:
    def get_session_override() -> Generator[Session]:
        yield session

    def get_broker_override() -> RabbitmqBroker:
        return broker

    def get_blob_storage_override() -> BlobStorage:
        return blob_storage

    monkeypatch.setattr("image_processor.main.get_broker", get_broker_override)
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_blob_storage] = get_blob_storage_override
    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_broker] = get_broker_override
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_blob_storage.cache_clear()


@pytest.fixture()
def make_image(session: Session) -> Callable[..., Image]:
    def factory(
        *,
        filename: str = "original.png",
        content_type: str = "image/png",
        size_bytes: int = 100,
        blob_key: str | None = None,
        status: ProcessingStatus = ProcessingStatus.pending_upload,
    ) -> Image:
        image = Image(
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            blob_key=blob_key,
            status=status,
        )
        session.add(image)
        session.commit()
        session.refresh(image)
        return image

    return factory


@pytest.fixture()
def reserve_upload(client: TestClient) -> Callable[..., str]:
    def factory(*, filename: str = "photo.png", size_bytes: int = 3) -> str:
        response = client.post(
            "/images/uploads",
            json={"filename": filename, "size_bytes": size_bytes},
        )
        assert response.status_code == 201
        upload_url = response.json()["upload_url"]
        assert isinstance(upload_url, str)
        assert upload_url.startswith("http://testserver/images/uploads/")
        return upload_url

    return factory
