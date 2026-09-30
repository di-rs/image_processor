from functools import lru_cache
from pathlib import Path

from ..config import get_settings


class BlobStorageError(Exception):
    pass


class BlobStorage:
    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir

    def delete(self, storage_path: str | None) -> None:
        if storage_path is None:
            return

        root = self._storage_dir.resolve()
        try:
            resolved = Path(storage_path).resolve()
            if not resolved.is_relative_to(root):
                raise BlobStorageError(
                    "Refusing to delete file outside storage root"
                    f" path={storage_path}"
                )
            resolved.unlink(missing_ok=True)
        except OSError as exc:
            raise BlobStorageError(
                f"Failed to delete stored file path={storage_path}"
            ) from exc


@lru_cache
def get_blob_storage() -> BlobStorage:
    return BlobStorage(Path(get_settings().storage_dir))
