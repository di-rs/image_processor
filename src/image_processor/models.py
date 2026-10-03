from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Annotated

from pydantic import StringConstraints, field_validator
from sqlalchemy import BigInteger, Column, DateTime
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProcessingStatus(StrEnum):
    pending_upload = auto()
    uploading = auto()
    uploaded = auto()
    queued = auto()
    processing = auto()
    failed = auto()
    finished = auto()


Filename = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
ContentType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=127),
]


class ImageBase(SQLModel):
    filename: Filename
    content_type: ContentType


class Image(ImageBase, table=True):
    id: int = Field(default=None, primary_key=True)
    status: ProcessingStatus = Field(default=ProcessingStatus.uploaded)

    size_bytes: int = Field(sa_type=BigInteger)
    blob_key: str | None = Field(default=None, unique=True, index=True)
    upload_expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    width: int | None = None
    height: int | None = None
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=utc_now,
        ),
    )


class ImageUploadCreate(SQLModel):
    filename: Filename
    size_bytes: int = Field(gt=0)


class ImageUploadRead(SQLModel):
    upload_url: str


class ImageUpdate(SQLModel):
    filename: Filename | None = None
    content_type: ContentType | None = None

    @field_validator("filename", "content_type", mode="before")
    @classmethod
    def reject_null_metadata(cls, value: object) -> object:
        if value is None:
            raise ValueError("must not be null")
        return value


class ImageRead(ImageBase):
    original_url: str | None = None
    id: int
    status: ProcessingStatus
    size_bytes: int
    width: int | None
    height: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_image(cls, image: Image, *, original_url: str) -> "ImageRead":
        result = cls.model_validate(image)
        if image.blob_key is not None and image.status not in {
            ProcessingStatus.pending_upload,
            ProcessingStatus.uploading,
        }:
            result.original_url = original_url
        return result
