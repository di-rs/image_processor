from collections import Counter
from collections.abc import Callable
from io import BytesIO
from random import Random

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PillowImage
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from image_processor import crud
from image_processor.domain.blob_key import BlobKey
from image_processor.domain.images import (
    ImageStatus,
    InvalidImageStateError,
    UploadedImage,
)
from image_processor.models import MAX_FILENAME_LENGTH, Image, ProcessingStatus
from image_processor.services.blob_storage import (
    BlobStorage,
    TemporaryImageFile,
)
from image_processor.services.image_processing import (
    ProcessingContext,
    extract_dimensions,
    process_image,
    shuffle_pixels,
)


def generated_image(session: Session, source: Image) -> Image:
    return session.exec(
        select(Image).where(Image.original_image == source.id)
    ).one()


@pytest.fixture(autouse=True)
def seeded_shuffle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "image_processor.services.image_processing.Random", lambda: Random(42)
    )


def test_processing_creates_finished_linked_image(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
) -> None:
    source = make_uploaded_image()
    process_image(session, source, blob_storage)
    result = generated_image(session, source)

    session.refresh(source)
    assert source.status == ProcessingStatus.finished
    assert source.original_image is None
    assert (source.width, source.height) == (3, 2)
    assert result.id != source.id
    assert result.blob_key is not None
    assert result.blob_key != source.blob_key
    assert result.filename == "original-shuffled.png"
    assert result.content_type == "image/png"
    assert result.status == ProcessingStatus.finished
    assert result.upload_expires_at is None
    assert (result.width, result.height) == (3, 2)
    path = blob_storage.get_image_path(result.blob_key)
    assert result.size_bytes == path.stat().st_size
    assert len(session.exec(select(Image)).all()) == 2


def test_shuffle_preserves_pixels_and_original_bytes(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
    png_bytes: bytes,
) -> None:
    source = make_uploaded_image()
    assert source.blob_key is not None
    original_path = blob_storage.get_image_path(source.blob_key)
    process_image(session, source, blob_storage)
    result = generated_image(session, source)
    assert result.blob_key is not None
    assert original_path.read_bytes() == png_bytes

    with (
        PillowImage.open(original_path) as original,
        PillowImage.open(
            blob_storage.get_image_path(result.blob_key)
        ) as shuffled,
    ):
        original_pixels = original.get_flattened_data()
        shuffled_pixels = shuffled.get_flattened_data()
        assert shuffled.format == "PNG"
        assert shuffled.size == original.size
        assert Counter(shuffled_pixels) == Counter(original_pixels)
        assert shuffled_pixels != original_pixels


@pytest.mark.parametrize("mode", ["1", "L", "LA", "P", "RGB", "RGBA", "I;16"])
def test_shuffle_preserves_supported_pixel_modes(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
    mode: str,
) -> None:
    with PillowImage.new(mode, (3, 2)) as original:
        if mode == "RGBA":
            original.putdata(
                [(10, 20, 30, alpha) for alpha in (0, 50, 100, 150, 200, 255)]
            )
        elif mode == "LA":
            original.putdata([(index * 30, index * 40) for index in range(6)])
        elif mode == "RGB":
            original.putdata([(index * 30, 10, 20) for index in range(6)])
        elif mode == "1":
            original.putdata([0, 255, 0, 255, 0, 255])
        else:
            original.putdata([0, 1, 2, 3, 4, 5])
        if mode == "P":
            original.putpalette(
                [value for value in range(256) for _ in range(3)]
            )
            original.info["transparency"] = 0
        with BytesIO() as output:
            original.save(output, format="PNG")
            data = output.getvalue()

    source = make_uploaded_image(data=data)
    process_image(session, source, blob_storage)
    result = generated_image(session, source)
    assert result.blob_key is not None
    with (
        PillowImage.open(BytesIO(data)) as original,
        PillowImage.open(
            blob_storage.get_image_path(result.blob_key)
        ) as shuffled,
    ):
        assert shuffled.mode == original.mode
        assert Counter(shuffled.get_flattened_data()) == Counter(
            original.get_flattened_data()
        )
        if mode == "P":
            assert shuffled.getpalette() == original.getpalette()
            assert shuffled.info["transparency"] == 0


def test_single_pixel_image_is_valid(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
) -> None:
    with PillowImage.new("RGBA", (1, 1), (10, 20, 30, 40)) as original:
        with BytesIO() as output:
            original.save(output, format="PNG")
            data = output.getvalue()
    source = make_uploaded_image(data=data)
    process_image(session, source, blob_storage)
    result = generated_image(session, source)
    assert result.blob_key is not None
    with PillowImage.open(
        blob_storage.get_image_path(result.blob_key)
    ) as image:
        assert image.size == (1, 1)
        assert image.getpixel((0, 0)) == (10, 20, 30, 40)


def test_generated_filename_respects_model_limit(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
) -> None:
    source = make_uploaded_image(
        filename="x" * (MAX_FILENAME_LENGTH - len(".png")) + ".png"
    )
    process_image(session, source, blob_storage)
    result = generated_image(session, source)
    assert len(result.filename) == MAX_FILENAME_LENGTH
    assert result.filename.endswith("-shuffled.png")


def test_dimensions_are_available_to_the_next_processor(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
) -> None:
    source = make_uploaded_image()

    def check_dimensions(context: ProcessingContext) -> None:
        assert (context.image.width, context.image.height) == (3, 2)
        shuffle_pixels(context)

    process_image(
        session,
        source,
        blob_storage,
        processors=(extract_dimensions, check_dimensions),
    )
    assert generated_image(session, source).width == 3


@pytest.mark.parametrize(
    ("exception", "expected_status"),
    [
        (ValueError("processor failed"), ProcessingStatus.failed),
        (SQLAlchemyError("database failed"), ProcessingStatus.processing),
    ],
)
def test_processor_failure_removes_generated_row_and_blob(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
    exception: Exception,
    expected_status: ProcessingStatus,
) -> None:
    source = make_uploaded_image()
    assert source.blob_key is not None
    original_bytes = blob_storage.get_image_path(source.blob_key).read_bytes()

    def fail(context: ProcessingContext) -> None:
        raise exception

    with pytest.raises(type(exception), match=str(exception)):
        process_image(
            session,
            source,
            blob_storage,
            processors=(extract_dimensions, shuffle_pixels, fail),
        )
    session.refresh(source)
    assert source.status == expected_status
    assert session.exec(select(Image)).all() == [source]
    assert {path.name for path in blob_storage.path.iterdir()} == {
        source.blob_key
    }
    assert (
        blob_storage.get_image_path(source.blob_key).read_bytes()
        == original_bytes
    )


def test_storage_publication_failure_removes_generated_upload(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_uploaded_image()

    def fail_publish(
        storage: BlobStorage, file: TemporaryImageFile, key: BlobKey
    ) -> None:
        raise OSError("storage unavailable")

    monkeypatch.setattr(BlobStorage, "_publish", fail_publish)
    with pytest.raises(OSError, match="storage unavailable"):
        process_image(session, source, blob_storage)
    session.refresh(source)
    assert source.status == ProcessingStatus.failed
    assert session.exec(select(Image)).all() == [source]
    assert {path.name for path in blob_storage.path.iterdir()} == {
        source.blob_key
    }


def test_final_database_failure_cleans_up_and_allows_retry(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_uploaded_image()
    update_status = crud.update_image_status

    def fail_finish(
        db_session: Session, image: Image, state: UploadedImage
    ) -> None:
        if state.status == ImageStatus.finished:
            raise SQLAlchemyError("commit unavailable")
        update_status(db_session, image, state)

    with monkeypatch.context() as patch:
        patch.setattr(crud, "update_image_status", fail_finish)
        with pytest.raises(SQLAlchemyError, match="commit unavailable"):
            process_image(session, source, blob_storage)
    session.refresh(source)
    assert source.status == ProcessingStatus.processing
    assert session.exec(select(Image)).all() == [source]
    assert {path.name for path in blob_storage.path.iterdir()} == {
        source.blob_key
    }
    process_image(session, source, blob_storage)
    assert generated_image(session, source).status == ProcessingStatus.finished
    assert len(session.exec(select(Image)).all()) == 2


def test_invalid_image_marks_source_failed(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
) -> None:
    source = make_uploaded_image(data=b"not an image")
    with pytest.raises(PillowImage.UnidentifiedImageError):
        process_image(session, source, blob_storage)
    session.refresh(source)
    assert source.status == ProcessingStatus.failed
    assert session.exec(select(Image)).all() == [source]


def test_finished_generated_image_cannot_be_processed_again(
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
) -> None:
    source = make_uploaded_image()
    process_image(session, source, blob_storage)
    result = generated_image(session, source)
    with pytest.raises(InvalidImageStateError):
        process_image(session, result, blob_storage)
    assert len(session.exec(select(Image)).all()) == 2


def test_api_returns_generated_image_link_and_bytes(
    client: TestClient,
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
) -> None:
    source = make_uploaded_image()
    process_image(session, source, blob_storage)
    result = generated_image(session, source)
    response = client.get(f"/images/{result.id}")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["original_image"] == source.id
    assert metadata["width"] == 3
    assert metadata["height"] == 2
    assert metadata["status"] == "finished"
    assert result.blob_key is not None
    response = client.get(metadata["original_url"])
    assert response.status_code == 200
    assert (
        response.content
        == blob_storage.get_image_path(result.blob_key).read_bytes()
    )
    listed = client.get("/images").json()
    assert {item["id"]: item["original_image"] for item in listed} == {
        source.id: None,
        result.id: source.id,
    }


def test_deleting_source_keeps_generated_image_and_clears_link(
    client: TestClient,
    session: Session,
    blob_storage: BlobStorage,
    make_uploaded_image: Callable[..., Image],
) -> None:
    source = make_uploaded_image()
    process_image(session, source, blob_storage)
    result = generated_image(session, source)
    assert result.blob_key is not None
    result_path = blob_storage.get_image_path(result.blob_key)
    response = client.delete(f"/images/{source.id}")
    assert response.status_code == 204
    session.refresh(result)
    assert result.original_image is None
    assert result_path.is_file()
    assert client.get(f"/images/{result.id}").status_code == 200
