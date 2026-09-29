from datetime import UTC, datetime
from enum import StrEnum, auto

from sqlalchemy import BigInteger, Column, DateTime
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProcessingStatus(StrEnum):
    awaiting_upload = auto()
    uploaded = auto()
    queued = auto()
    processing = auto()
    failed = auto()
    finished = auto()


class ImageBase(SQLModel):
    filename: str = Field(max_length=255)
    content_type: str = Field(max_length=127)


class Image(ImageBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    status: ProcessingStatus = Field(default=ProcessingStatus.awaiting_upload)
    storage_path: str | None = Field(default=None, max_length=1024)
    size_bytes: int | None = Field(default=None, sa_type=BigInteger)
    width: int | None = Field(default=None)
    height: int | None = Field(default=None)
    upload_token: str | None = Field(default=None, max_length=64, unique=True)
    upload_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
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


class ImageCreate(ImageBase):
    pass


class ImageUpdate(SQLModel):
    filename: str | None = Field(default=None, max_length=255)
    content_type: str | None = Field(default=None, max_length=127)


class ImageRead(ImageBase):
    id: int
    status: ProcessingStatus
    size_bytes: int | None
    width: int | None
    height: int | None
    created_at: datetime
    updated_at: datetime
