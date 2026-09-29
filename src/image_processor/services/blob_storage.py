import logging
from pathlib import Path

from ..config import get_settings

logger = logging.getLogger(__name__)


def get_storage_dir() -> Path:
    return Path(get_settings().storage_dir)


def delete(storage_path: str | None) -> None:
    if storage_path is None:
        return

    path = Path(storage_path)
    root = get_storage_dir().resolve()
    try:
        resolved = path.resolve()
    except OSError:
        logger.warning("Failed to resolve stored file path=%s", storage_path)
        return

    if not resolved.is_relative_to(root):
        logger.warning(
            "Refusing to delete file outside storage root path=%s",
            storage_path,
        )
        return

    try:
        resolved.unlink(missing_ok=True)
    except OSError:
        logger.warning("Failed to delete stored file path=%s", storage_path)
