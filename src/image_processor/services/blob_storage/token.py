from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import cast

from pydantic import Field, ValidationError

from ...domain.images import (
    ImageDomainError,
    ImageDomainModel,
    UploadNotFoundError,
)


class UploadToken(ImageDomainModel):
    """Claims from a signed upload permit. The permit itself is not stored."""

    blob_key: str = Field(min_length=1, max_length=64)
    expires_at: datetime

    @classmethod
    def issue(
        cls,
        *,
        filename: str,
        content_type: str,
        ttl: timedelta,
    ) -> "UploadToken":
        if ttl <= timedelta(0):
            raise ImageDomainError("ttl must be positive")
        return cls(
            filename=filename,
            content_type=content_type,
            blob_key=token_urlsafe(32),
            expires_at=datetime.now(UTC) + ttl,
        )

    def claims(self) -> dict[str, str]:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "blob_key": self.blob_key,
        }

    @classmethod
    def from_claims(
        cls,
        payload: object,
        *,
        signed_at: datetime,
        ttl: timedelta,
    ) -> "UploadToken":
        try:
            filename, content_type, blob_key = _claims(payload)
            return cls(
                filename=filename,
                content_type=content_type,
                blob_key=blob_key,
                expires_at=signed_at + ttl,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise UploadNotFoundError("Upload token was not found") from exc


def _claims(payload: object) -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        raise TypeError("upload token payload is invalid")
    claims = cast(dict[object, object], payload)
    filename = claims.get("filename")
    content_type = claims.get("content_type")
    blob_key = claims.get("blob_key")
    if (
        not isinstance(filename, str)
        or not isinstance(content_type, str)
        or not isinstance(blob_key, str)
    ):
        raise TypeError("upload token payload is invalid")
    return filename, content_type, blob_key
