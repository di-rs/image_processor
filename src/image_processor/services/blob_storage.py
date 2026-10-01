from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from shutil import copyfileobj
from typing import BinaryIO

from ..config import DEFAULT_BLOB_STORAGE_PATH, get_settings
from ..domain.blob_key import BlobKey


@dataclass(frozen=True)
class BlobStorage:
    path: Path = DEFAULT_BLOB_STORAGE_PATH

    def create_key(self) -> BlobKey:
        return BlobKey.create()

    def create_image(self, blob_key: BlobKey, file: BinaryIO) -> None:
        path = self._image_path(blob_key)
        self.path.mkdir(parents=True, exist_ok=True)
        # Exclusive creation must succeed before cleanup can own this path.
        with path.open("xb") as destination:
            try:
                copyfileobj(file, destination)
                destination.flush()
            except BaseException:
                path.unlink(missing_ok=True)
                raise

    def delete_image(self, blob_key: BlobKey) -> None:
        self._image_path(blob_key).unlink(missing_ok=True)

    def _image_path(self, blob_key: BlobKey) -> Path:
        return self.path / blob_key.value


@lru_cache
def get_blob_storage() -> BlobStorage:
    return BlobStorage(path=get_settings().blob_storage_path)
