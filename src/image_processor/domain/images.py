from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto
from secrets import token_urlsafe

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    TypeAdapter,
    field_validator,
)

_aware_datetime = TypeAdapter(AwareDatetime)


class ImageStatus(StrEnum):
    uploaded = auto()
    queued = auto()
    processing = auto()
    failed = auto()
    finished = auto()


class ImageDomainError(Exception):
    pass


class UploadExpiredError(ImageDomainError):
    pass


class InvalidImageStateError(ImageDomainError):
    pass


def _strip_required_text(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
    return value


class ImageDomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=127)
    blob_key: str = Field(min_length=1, max_length=64)

    @field_validator(
        "filename",
        "content_type",
        "blob_key",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return _strip_required_text(value)


class UploadedImage(ImageDomainModel):
    """An image whose bytes are already in storage."""

    size_bytes: PositiveInt
    width: PositiveInt
    height: PositiveInt
    status: ImageStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime

    def enqueue(self, *, now: datetime) -> "UploadedImage":
        if self.status is not ImageStatus.uploaded:
            raise InvalidImageStateError("Only an uploaded image can be queued")
        return self.model_copy(
            update={
                "status": ImageStatus.queued,
                "updated_at": _aware_datetime.validate_python(now),
            }
        )


class PreuploadedImage(ImageDomainModel):
    """A reserved upload slot. Bytes are not in storage yet."""

    upload_token: str = Field(min_length=1, max_length=64)
    upload_expires_at: AwareDatetime

    @field_validator("upload_token", mode="before")
    @classmethod
    def strip_token(cls, value: object) -> object:
        return _strip_required_text(value)

    @classmethod
    def create(
        cls,
        *,
        filename: str,
        content_type: str,
        ttl: timedelta,
        now: datetime | None = None,
    ) -> "PreuploadedImage":
        if ttl <= timedelta(0):
            raise ImageDomainError("ttl must be positive")
        if now is None:
            now = datetime.now(UTC)
        expires_at = _aware_datetime.validate_python(now) + ttl
        return cls(
            filename=filename,
            content_type=content_type,
            blob_key=token_urlsafe(32),
            upload_token=token_urlsafe(32),
            upload_expires_at=expires_at,
        )

    def is_expired(self, now: datetime) -> bool:
        return _aware_datetime.validate_python(now) >= self.upload_expires_at

    def upload(
        self,
        *,
        size_bytes: int,
        width: int,
        height: int,
        now: datetime,
    ) -> UploadedImage:
        """Turn this reservation into an uploaded image."""
        if self.is_expired(now):
            raise UploadExpiredError("Upload token has expired")
        uploaded_at = _aware_datetime.validate_python(now)
        return UploadedImage(
            filename=self.filename,
            content_type=self.content_type,
            blob_key=self.blob_key,
            size_bytes=size_bytes,
            width=width,
            height=height,
            status=ImageStatus.uploaded,
            created_at=uploaded_at,
            updated_at=uploaded_at,
        )
