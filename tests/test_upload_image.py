from sqlmodel import Session

from image_processor.models import ProcessingStatus
from image_processor.services.blob_storage import BlobStorage
from image_processor.services.images import create_upload_target, upload_image


def test_upload_image_stores_bytes_and_creates_the_row(
    session: Session,
    blob_storage: BlobStorage,
) -> None:
    target = create_upload_target(
        blob_storage,
        filename="cat.png",
        content_type="image/png",
    )
    token = target.upload_url.removeprefix("/images/uploads/")

    image = upload_image(
        session,
        blob_storage,
        upload_token=token,
        data=b"png",
        width=10,
        height=20,
    )

    assert image.id == 1
    assert image.status is ProcessingStatus.uploaded
    assert image.filename == "cat.png"
    assert image.size_bytes == 3
    assert image.width == 10
    assert image.height == 20
    assert blob_storage.path_for(image.blob_key).read_bytes() == b"png"
