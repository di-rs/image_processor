from functools import lru_cache
from pathlib import Path
from secrets import token_urlsafe

from ..config import get_settings


class BlobStorageError(Exception):
    pass


class BlobStorage:
    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir

    def reserve_path(self, filename: str) -> str:
        name = Path(filename.strip()).name
        if not name or name in {".", ".."}:
            raise BlobStorageError(f"Invalid filename filename={filename}")
        root = self._storage_dir.resolve()
        path = (root / token_urlsafe(16) / name).resolve()
        if not path.is_relative_to(root):
            raise BlobStorageError(
                f"Refusing to reserve file outside storage root path={path}"
            )
        return str(path)

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
