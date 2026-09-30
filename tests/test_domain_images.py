import pytest

from image_processor.domain.images import (
    ImageStatus,
    InvalidImageStateError,
    UploadedImage,
)


def _uploaded(**overrides: object) -> UploadedImage:
    values: dict[str, object] = {
        "filename": "cat.png",
        "content_type": "image/png",
        "size_bytes": 128,
        "width": 10,
        "height": 20,
        "status": ImageStatus.uploaded,
    }
    values.update(overrides)
    return UploadedImage(**values)  # type: ignore[arg-type]


def test_enqueue_is_only_valid_after_upload() -> None:
    image = _uploaded()

    queued = image.enqueue()

    assert queued.status is ImageStatus.queued
    assert image.status is ImageStatus.uploaded
    with pytest.raises(InvalidImageStateError):
        queued.enqueue()
