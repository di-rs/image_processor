from enum import StrEnum, auto

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
)


class ImageStatus(StrEnum):
    uploaded = auto()
    queued = auto()
    processing = auto()
    failed = auto()
    finished = auto()


class ImageDomainError(Exception):
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


class UploadedImage(ImageDomainModel):
    """An image whose bytes are already in storage."""

    size_bytes: PositiveInt
    status: ImageStatus = ImageStatus.uploaded

    def enqueue(self) -> "UploadedImage":
        if self.status is not ImageStatus.uploaded:
            raise InvalidImageStateError("Only an uploaded image can be queued")
        return self.model_copy(update={"status": ImageStatus.queued})
