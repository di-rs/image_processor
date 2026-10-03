from asyncio import to_thread
from collections.abc import AsyncIterable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from os import link
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from ..config import DEFAULT_BLOB_STORAGE_PATH, get_settings
from ..domain.blob_key import BlobKey
from ..domain.images import ImageNotFoundError, InvalidImageUploadError


class TemporaryImageFile(Protocol):
    @property
    def name(self) -> str: ...

    def write(self, data: bytes, /) -> int: ...

    def flush(self) -> None: ...


@dataclass(frozen=True)
class BlobStorage:
    path: Path = DEFAULT_BLOB_STORAGE_PATH

    def create_key(self) -> BlobKey:
        return BlobKey.create()

    async def create_image(
        self,
        blob_key: str | BlobKey,
        chunks: AsyncIterable[bytes],
        size_bytes: int,
    ) -> None:
        if isinstance(blob_key, str):
            blob_key = BlobKey(blob_key)
        with self._temporary_file() as file:
            await self._write_chunks(file, chunks, size_bytes)
            self._publish(file, blob_key)

    @contextmanager
    def _temporary_file(self) -> Generator[TemporaryImageFile]:
        self.path.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w+b", dir=self.path, prefix=".upload-"
        ) as file:
            yield file

    async def _write_chunks(
        self,
        file: TemporaryImageFile,
        chunks: AsyncIterable[bytes],
        size_bytes: int,
    ) -> None:
        received = 0
        async for chunk in chunks:
            received += len(chunk)
            if received > size_bytes:
                raise InvalidImageUploadError(
                    "Uploaded bytes exceed the declared size"
                )
            await to_thread(file.write, chunk)
        if received != size_bytes:
            raise InvalidImageUploadError(
                "Uploaded bytes do not match the declared size"
            )
        await to_thread(file.flush)

    def _publish(self, file: TemporaryImageFile, blob_key: BlobKey) -> None:
        # Publish without overwriting an existing key or copying bytes.
        link(file.name, self._image_path(blob_key))

    def delete_image(self, blob_key: str | BlobKey) -> None:
        self._image_path(blob_key).unlink(missing_ok=True)

    def get_image_path(self, blob_key: str | BlobKey) -> Path:
        path = self._image_path(blob_key)
        if not path.is_file():
            raise ImageNotFoundError("Image bytes not found")
        return path

    def _image_path(self, blob_key: str | BlobKey) -> Path:
        if isinstance(blob_key, str):
            blob_key = BlobKey(blob_key)
        return self.path / blob_key.value


@lru_cache
def get_blob_storage() -> BlobStorage:
    return BlobStorage(path=get_settings().blob_storage_path)
