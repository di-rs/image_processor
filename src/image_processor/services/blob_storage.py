from functools import lru_cache
from pathlib import Path

from ..config import get_settings


class BlobStorageError(Exception):
    pass


class BlobStorage:
    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir

    def path_for(self, blob_key: str) -> Path:
        return self._storage_dir / blob_key

    def create_upload_url(self, upload_token: str) -> str:
        return f"/images/uploads/{upload_token}"

    def save(self, blob_key: str, data: bytes) -> int:
        if not data:
            raise BlobStorageError("Refusing to save an empty file")

        path = self.path_for(blob_key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            raise BlobStorageError(
                f"Failed to save file blob_key={blob_key}"
            ) from exc
        return len(data)

    def delete(self, blob_key: str | None) -> None:
        if blob_key is None:
            return

        try:
            self.path_for(blob_key).unlink(missing_ok=True)
        except OSError as exc:
            raise BlobStorageError(
                f"Failed to delete stored file blob_key={blob_key}"
            ) from exc


@lru_cache
def get_blob_storage() -> BlobStorage:
    return BlobStorage(Path(get_settings().storage_dir))
