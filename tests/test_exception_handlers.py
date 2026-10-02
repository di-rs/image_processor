import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from image_processor.app.exception_handlers import register_exception_handlers
from image_processor.domain.images import (
    ImageDomainError,
    ImageNotFoundError,
    InvalidImageStateError,
    InvalidImageUploadError,
    UploadExpiredError,
)


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (InvalidImageStateError("Only an uploaded image can be queued"), 409),
        (ImageDomainError("Invalid image metadata"), 422),
        (InvalidImageUploadError("Invalid upload metadata"), 422),
        (ImageNotFoundError("Image not found"), 404),
        (UploadExpiredError("Upload URL has expired"), 410),
    ],
)
def test_domain_error_returns_expected_status_and_detail(
    error: ImageDomainError, status_code: int
) -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise error

    with TestClient(app) as client:
        response = client.get("/boom")

    assert response.status_code == status_code
    assert response.json() == {"detail": str(error)}


def test_integrity_error_returns_conflict_without_database_details() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise IntegrityError("private query", {}, Exception("private error"))

    with TestClient(app) as client:
        response = client.get("/boom")

    assert response.status_code == 409
    assert response.json() == {"detail": "Data conflict occured."}
