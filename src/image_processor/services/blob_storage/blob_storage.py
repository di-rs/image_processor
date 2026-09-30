from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import cast

from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

from ...config import get_settings
from ...domain.images import UploadExpiredError, UploadNotFoundError
from .token import UploadToken

_UPLOAD_TOKEN_SALT = "image-upload"


class BlobStorageError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class BlobStorage:
    storage_dir: Path
    secret: str = field(repr=False, kw_only=True)
    upload_ttl: timedelta = field(kw_only=True)
    _serializer: URLSafeTimedSerializer = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.upload_ttl <= timedelta(0):
            raise ValueError("upload ttl must be positive")
        if not self.secret:
            raise ValueError("upload token secret is missing")
        object.__setattr__(
            self,
            "_serializer",
            URLSafeTimedSerializer(self.secret, salt=_UPLOAD_TOKEN_SALT),
        )

    def path_for(self, blob_key: str) -> Path:
        return self.storage_dir / blob_key

    def issue_upload_token(self, *, filename: str, content_type: str) -> str:
        permit = UploadToken.issue(
            filename=filename,
            content_type=content_type,
            ttl=self.upload_ttl,
        )
        return self._serializer.dumps(permit.claims())

    def parse_upload_token(self, value: str) -> UploadToken:
        try:
            payload, signed_at = cast(
                tuple[object, object],
                self._serializer.loads(
                    value,
                    max_age=int(self.upload_ttl.total_seconds()),
                    return_timestamp=True,
                ),
            )
        except SignatureExpired as exc:
            raise UploadExpiredError("Upload token has expired") from exc
        except BadData as exc:
            raise UploadNotFoundError("Upload token was not found") from exc
        if not isinstance(signed_at, datetime):
            raise UploadNotFoundError("Upload token was not found")
        return UploadToken.from_claims(
            payload,
            signed_at=signed_at,
            ttl=self.upload_ttl,
        )

    def create_upload_url(self, upload_token: str) -> str:
        return f"/images/uploads/{upload_token}"

    def save(self, blob_key: str, data: bytes) -> int:
        if not data:
            raise BlobStorageError("Refusing to save an empty file")

        path = self.path_for(blob_key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            raise BlobStorageError(
                f"Failed to save file blob_key={blob_key}"
            ) from exc
        return len(data)

    def delete(self, blob_key: str | None) -> None:
        if blob_key is None:
            return

        try:
            self.path_for(blob_key).unlink(missing_ok=True)
        except OSError as exc:
            raise BlobStorageError(
                f"Failed to delete stored file blob_key={blob_key}"
            ) from exc


@lru_cache
def get_blob_storage() -> BlobStorage:
    settings = get_settings()
    return BlobStorage(
        Path(settings.storage_dir),
        secret=settings.upload_token_secret,
        upload_ttl=timedelta(minutes=settings.upload_ttl_minutes),
    )
