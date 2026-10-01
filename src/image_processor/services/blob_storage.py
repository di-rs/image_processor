from functools import lru_cache
from secrets import token_urlsafe


class BlobStorage:
    def create_key(self) -> str:
        """Generate an opaque key independent of client filenames and paths."""
        return token_urlsafe(32)


@lru_cache
def get_blob_storage() -> BlobStorage:
    return BlobStorage()
