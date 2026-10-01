from datetime import UTC, datetime
from enum import StrEnum, auto

from sqlalchemy import BigInteger, Column, DateTime
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProcessingStatus(StrEnum):
    pending_upload = auto()
    uploaded = auto()
    queued = auto()
    processing = auto()
    failed = auto()
    finished = auto()


class ImageBase(SQLModel):
    filename: str = Field(max_length=255)
    content_type: str = Field(max_length=127)


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
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)


class ImageUploadRead(SQLModel):
    upload_url: str


class ImageUpdate(SQLModel):
    filename: str | None = Field(default=None, max_length=255)
    content_type: str | None = Field(default=None, max_length=127)


class ImageRead(ImageBase):
    id: int
    status: ProcessingStatus
    size_bytes: int
    width: int | None
    height: int | None
    created_at: datetime
    updated_at: datetime
