from image_processor.services.blob_storage import BlobStorage
from image_processor.services.images import create_upload_target


def test_create_upload_target_does_not_persist(
    blob_storage: BlobStorage,
) -> None:
    target = create_upload_target(
        blob_storage,
        filename=" cat.png ",
        content_type="image/png",
    )

    token = target.upload_url.removeprefix("/images/uploads/")
    assert token
    assert target.upload_url == f"/images/uploads/{token}"
