from fastapi import FastAPI
from fastapi.testclient import TestClient

from image_processor.domain.images import (
    ImageDomainError,
    InvalidImageStateError,
)
from image_processor.exception_handlers import register_exception_handlers


def _client_for(error: ImageDomainError) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise error

    return TestClient(app)


def test_invalid_image_state_error_is_conflict() -> None:
    response = _client_for(
        InvalidImageStateError("Only an uploaded image can be queued")
    ).get("/boom")

    assert response.status_code == 409
    assert response.json() == {"detail": "Only an uploaded image can be queued"}


def test_image_domain_error_is_unprocessable() -> None:
    response = _client_for(ImageDomainError("Invalid image metadata")).get(
        "/boom"
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid image metadata"}
