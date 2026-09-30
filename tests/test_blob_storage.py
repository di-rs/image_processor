from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from image_processor.domain.images import (
    UploadExpiredError,
    UploadNotFoundError,
)
from image_processor.services.blob_storage import BlobStorage, BlobStorageError

SECRET = "test-secret"
TTL = timedelta(minutes=15)


def _storage(
    tmp_path: Path,
    *,
    secret: str = SECRET,
    upload_ttl: timedelta = TTL,
) -> BlobStorage:
    return BlobStorage(tmp_path, secret=secret, upload_ttl=upload_ttl)


def test_save_writes_bytes_for_a_blob_key(tmp_path: Path) -> None:
    storage = _storage(tmp_path)

    size = storage.save("blob-key", b"png")

    assert size == 3
    assert storage.path_for("blob-key").read_bytes() == b"png"


def test_upload_url_uses_the_upload_token(tmp_path: Path) -> None:
    storage = _storage(tmp_path)

    assert storage.create_upload_url("token") == "/images/uploads/token"


def test_save_refuses_an_empty_file(tmp_path: Path) -> None:
    storage = _storage(tmp_path)

    with pytest.raises(BlobStorageError):
        storage.save("blob-key", b"")


def test_issue_encodes_a_token_that_can_be_parsed(tmp_path: Path) -> None:
    before = datetime.now(UTC)
    storage = _storage(tmp_path)

    token = storage.parse_upload_token(
        storage.issue_upload_token(
            filename=" cat.png ",
            content_type="image/png",
        )
    )
    after = datetime.now(UTC)

    assert token.filename == "cat.png"
    assert token.content_type == "image/png"
    assert before + TTL <= token.expires_at + timedelta(seconds=1)
    assert token.expires_at <= after + TTL
    assert 1 <= len(token.blob_key) <= 64


def test_parse_rejects_a_tampered_token(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    encoded = storage.issue_upload_token(
        filename="cat.png",
        content_type="image/png",
    )
    payload, separator, rest = encoded.partition(".")
    tampered = f"{payload[:-1]}A{separator}{rest}"

    with pytest.raises(UploadNotFoundError):
        storage.parse_upload_token(tampered)


def test_parse_rejects_a_token_signed_with_another_secret(
    tmp_path: Path,
) -> None:
    issued = _storage(tmp_path, secret="other-secret").issue_upload_token(
        filename="cat.png",
        content_type="image/png",
    )

    with pytest.raises(UploadNotFoundError):
        _storage(tmp_path).parse_upload_token(issued)


def test_parse_rejects_an_expired_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signed_at = 1_000_000
    monkeypatch.setattr("time.time", lambda: signed_at)
    encoded = _storage(tmp_path).issue_upload_token(
        filename="cat.png",
        content_type="image/png",
    )
    monkeypatch.setattr(
        "time.time",
        lambda: signed_at + int(TTL.total_seconds()) + 1,
    )

    with pytest.raises(UploadExpiredError):
        _storage(tmp_path).parse_upload_token(encoded)


def test_parse_accepts_a_token_at_the_end_of_its_ttl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signed_at = 1_000_000
    monkeypatch.setattr("time.time", lambda: signed_at)
    encoded = _storage(tmp_path).issue_upload_token(
        filename="cat.png",
        content_type="image/png",
    )
    monkeypatch.setattr(
        "time.time",
        lambda: signed_at + int(TTL.total_seconds()),
    )

    token = _storage(tmp_path).parse_upload_token(encoded)

    assert token.expires_at == datetime.fromtimestamp(signed_at, UTC) + TTL


def test_refuses_a_missing_secret(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="secret"):
        BlobStorage(tmp_path, secret="", upload_ttl=TTL)


def test_refuses_a_non_positive_ttl(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ttl"):
        BlobStorage(tmp_path, secret=SECRET, upload_ttl=timedelta(0))
