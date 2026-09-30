from datetime import UTC, datetime, timedelta

import pytest

from image_processor.domain.images import ImageDomainError, UploadNotFoundError
from image_processor.services.blob_storage import UploadToken

TTL = timedelta(minutes=15)


def test_issue_builds_claims_that_can_be_restored() -> None:
    before = datetime.now(UTC)
    issued = UploadToken.issue(
        filename=" cat.png ",
        content_type="image/png",
        ttl=TTL,
    )
    after = datetime.now(UTC)

    restored = UploadToken.from_claims(
        issued.claims(),
        signed_at=before,
        ttl=TTL,
    )

    assert issued.filename == "cat.png"
    assert before + TTL <= issued.expires_at <= after + TTL
    assert restored.blob_key == issued.blob_key
    assert restored.expires_at == before + TTL


def test_issue_rejects_a_blank_filename() -> None:
    with pytest.raises(ValueError, match="blank"):
        UploadToken.issue(
            filename=" ",
            content_type="image/png",
            ttl=TTL,
        )


def test_issue_rejects_a_non_positive_ttl() -> None:
    with pytest.raises(ImageDomainError, match="ttl"):
        UploadToken.issue(
            filename="cat.png",
            content_type="image/png",
            ttl=timedelta(0),
        )


def test_from_claims_rejects_an_invalid_payload() -> None:
    with pytest.raises(UploadNotFoundError):
        UploadToken.from_claims(
            {"filename": " "},
            signed_at=datetime.now(UTC),
            ttl=TTL,
        )
