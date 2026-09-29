import logging
from pathlib import Path

from ..config import get_settings

logger = logging.getLogger(__name__)


class BlobStorageError(Exception):
    pass


def get_storage_dir() -> Path:
    return Path(get_settings().storage_dir)


def delete(storage_path: str | None) -> None:
    if storage_path is None:
        return

    root = get_storage_dir().resolve()
    try:
        resolved = Path(storage_path).resolve()
        if not resolved.is_relative_to(root):
            logger.error(
                "Refusing to delete file outside storage root path=%s",
                storage_path,
            )
            raise BlobStorageError
        resolved.unlink(missing_ok=True)
    except OSError as exc:
        logger.exception(
            "Failed to delete stored file path=%s error=%r",
            storage_path,
            exc,
        )
        raise BlobStorageError from exc
