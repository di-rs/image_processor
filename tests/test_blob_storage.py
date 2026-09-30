from pathlib import Path

import pytest

from image_processor.services.blob_storage import BlobStorage, BlobStorageError


def test_save_writes_bytes_for_a_blob_key(tmp_path: Path) -> None:
    storage = BlobStorage(tmp_path)

    size = storage.save("blob-key", b"png")

    assert size == 3
    assert storage.path_for("blob-key").read_bytes() == b"png"


def test_upload_url_uses_the_upload_token(tmp_path: Path) -> None:
    storage = BlobStorage(tmp_path)

    assert storage.create_upload_url("token") == "/images/uploads/token"


def test_save_refuses_an_empty_file(tmp_path: Path) -> None:
    storage = BlobStorage(tmp_path)

    with pytest.raises(BlobStorageError):
        storage.save("blob-key", b"")
