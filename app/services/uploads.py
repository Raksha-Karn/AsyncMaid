from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from app.config import settings
from app.models import UploadedFile

CHUNK_SIZE = 1024 * 1024


def _validate_csv_upload(file: UploadFile) -> str:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix != ".csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed",
        )
    return Path(filename).name


async def store_csv_upload(db: Session, *, file: UploadFile, owner_id: int) -> UploadedFile:
    original_filename = _validate_csv_upload(file)
    upload_id = str(uuid4())
    owner_upload_dir = settings.upload_dir / str(owner_id)
    owner_upload_dir.mkdir(parents=True, exist_ok=True)

    storage_path = owner_upload_dir / f"{upload_id}.csv"
    size_bytes = 0

    try:
        with storage_path.open("wb") as output_file:
            while chunk := await file.read(CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > settings.max_upload_size_bytes:
                    output_file.close()
                    storage_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"CSV file exceeds {settings.max_upload_size_bytes} bytes",
                    )
                output_file.write(chunk)
    finally:
        await file.close()

    if size_bytes == 0:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty",
        )

    uploaded_file = UploadedFile(
        id=upload_id,
        original_filename=original_filename,
        storage_path=str(storage_path),
        size_bytes=size_bytes,
        content_type=file.content_type,
        owner_id=owner_id,
    )
    db.add(uploaded_file)
    db.commit()
    db.refresh(uploaded_file)
    return uploaded_file
