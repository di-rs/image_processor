from datetime import datetime
from enum import StrEnum, auto
from mimetypes import guess_type

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    ValidationError,
    field_validator,
)


class ImageStatus(StrEnum):
    pending_upload = auto()
    uploaded = auto()
    queued = auto()
    processing = auto()
    failed = auto()
    finished = auto()


class ImageDomainError(Exception):
    pass


class InvalidImageUploadError(ImageDomainError):
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

    @field_validator("filename", "content_type", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return _strip_required_text(value)


class PendingImageUpload(ImageDomainModel):
    size_bytes: PositiveInt
    blob_key: str = Field(min_length=1)
    upload_expires_at: datetime
    status: ImageStatus = ImageStatus.pending_upload

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        if not value.startswith("image/") or value in {
            "image/gif",
            "image/svg+xml",
        }:
            raise InvalidImageUploadError(
                "Content type must identify an image other than GIF or SVG"
            )
        return value

    @staticmethod
    def create(
        *,
        filename: str,
        size_bytes: int,
        blob_key: str,
        upload_expires_at: datetime,
    ) -> "PendingImageUpload":
        filename = filename.strip()
        content_type, encoding = guess_type(filename)
        if content_type is None or encoding is not None:
            raise InvalidImageUploadError(
                "Filename must identify an image other than GIF or SVG"
            )
        try:
            return PendingImageUpload(
                filename=filename,
                content_type=content_type,
                size_bytes=size_bytes,
                blob_key=blob_key,
                upload_expires_at=upload_expires_at,
            )
        except ValidationError as exc:
            raise InvalidImageUploadError("Invalid upload metadata") from exc


class UploadedImage(ImageDomainModel):
    """An image whose bytes are already in storage."""

    size_bytes: PositiveInt
    status: ImageStatus = ImageStatus.uploaded

    def enqueue(self) -> "UploadedImage":
        if self.status is not ImageStatus.uploaded:
            raise InvalidImageStateError("Only an uploaded image can be queued")
        return self.model_copy(update={"status": ImageStatus.queued})
