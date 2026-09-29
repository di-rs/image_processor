from datetime import UTC, datetime
from enum import StrEnum, auto

from sqlmodel import Column, DateTime, Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProcessingStatus(StrEnum):
    uploaded = auto()
    queued = auto()
    processing = auto()
    failed = auto()
    finished = auto()


class Image(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    status: ProcessingStatus = Field(default=ProcessingStatus.uploaded)

    width: int
    height: int

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

