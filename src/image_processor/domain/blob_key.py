from dataclasses import dataclass
from re import fullmatch
from secrets import token_urlsafe

from .images import ImageDomainError


class InvalidBlobKeyError(ImageDomainError):
    pass


@dataclass(frozen=True)
class BlobKey:
    value: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.value, str)
            or fullmatch(r"[A-Za-z0-9_-]+", self.value) is None
        ):
            raise InvalidBlobKeyError("Invalid blob key")

    @staticmethod
    def create() -> "BlobKey":
        return BlobKey(token_urlsafe(32))

    def __str__(self) -> str:
        return self.value
