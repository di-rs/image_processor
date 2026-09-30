from fastapi import FastAPI
from fastapi.testclient import TestClient

from image_processor.domain.images import (
    ImageDomainError,
    InvalidImageStateError,
    UploadExpiredError,
    UploadNotFoundError,
)
from image_processor.exception_handlers import register_exception_handlers


def _client_for(error: ImageDomainError) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise error

    return TestClient(app)


def test_upload_not_found_error_is_not_found() -> None:
    response = _client_for(
        UploadNotFoundError("Upload token was not found")
    ).get("/boom")

    assert response.status_code == 404
    assert response.json() == {"detail": "Upload token was not found"}


def test_upload_expired_error_is_gone() -> None:
    response = _client_for(UploadExpiredError("Upload token has expired")).get(
        "/boom"
    )

    assert response.status_code == 410
    assert response.json() == {"detail": "Upload token has expired"}


def test_invalid_image_state_error_is_conflict() -> None:
    response = _client_for(
        InvalidImageStateError("Only an uploaded image can be queued")
    ).get("/boom")

    assert response.status_code == 409
    assert response.json() == {"detail": "Only an uploaded image can be queued"}


def test_image_domain_error_is_unprocessable() -> None:
    response = _client_for(ImageDomainError("ttl must be positive")).get(
        "/boom"
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "ttl must be positive"}
