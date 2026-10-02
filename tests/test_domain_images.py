import pytest

from image_processor.domain.images import (
    ImageStatus,
    InvalidImageStateError,
    UploadedImage,
)


def _uploaded(*, status: ImageStatus = ImageStatus.uploaded) -> UploadedImage:
    return UploadedImage(
        filename="cat.png",
        content_type="image/png",
        size_bytes=128,
        status=status,
    )


def test_enqueue_is_only_valid_after_upload() -> None:
    image = _uploaded()

    queued = image.enqueue()

    assert queued.status is ImageStatus.queued
    assert image.status is ImageStatus.uploaded


@pytest.mark.parametrize(
    "status",
    [status for status in ImageStatus if status is not ImageStatus.uploaded],
)
def test_enqueue_rejects_images_not_in_uploaded_state(
    status: ImageStatus,
) -> None:
    image = _uploaded(status=status)
    with pytest.raises(
        InvalidImageStateError, match="Only an uploaded image can be queued"
    ):
        image.enqueue()
    assert image.status is status


@pytest.mark.parametrize(
    "status", [ImageStatus.uploaded, ImageStatus.queued, ImageStatus.processing]
)
def test_start_processing(status: ImageStatus) -> None:
    image = _uploaded(status=status)
    processing = image.start_processing()

    assert processing.status is ImageStatus.processing
    assert image.status is status


def test_finish_processing_does_not_mutate_original() -> None:
    image = _uploaded(status=ImageStatus.processing)
    finished = image.finish_processing()
    assert finished.status is ImageStatus.finished
    assert image.status is ImageStatus.processing


def test_fail_processing_does_not_mutate_original() -> None:
    image = _uploaded(status=ImageStatus.processing)
    failed = image.fail_processing()
    assert failed.status is ImageStatus.failed
    assert image.status is ImageStatus.processing


@pytest.mark.parametrize("status", [ImageStatus.finished, ImageStatus.failed])
def test_terminal_images_are_not_processed(status: ImageStatus) -> None:
    with pytest.raises(InvalidImageStateError, match=status.value):
        _uploaded(status=status).start_processing()


@pytest.mark.parametrize(
    "status", [ImageStatus.pending_upload, ImageStatus.uploading]
)
def test_processing_requires_uploaded_bytes(status: ImageStatus) -> None:
    with pytest.raises(
        InvalidImageStateError,
        match="Only an image with uploaded bytes can be processed",
    ):
        _uploaded(status=status).start_processing()


@pytest.mark.parametrize(
    "status",
    [status for status in ImageStatus if status is not ImageStatus.processing],
)
def test_completion_requires_processing(status: ImageStatus) -> None:
    image = _uploaded(status=status)
    with pytest.raises(InvalidImageStateError):
        image.finish_processing()
    with pytest.raises(InvalidImageStateError):
        image.fail_processing()
