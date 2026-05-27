import pytest
from unittest.mock import MagicMock
from fastapi import UploadFile, HTTPException
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.services.uploads import _validate_csv_upload


def test_validate_csv_upload_success():
    file = MagicMock(spec=UploadFile)
    file.filename = "data.csv"
    result = _validate_csv_upload(file)
    assert result == "data.csv"


def test_validate_csv_upload_rejects_non_csv():
    file = MagicMock(spec=UploadFile)
    file.filename = "image.png"
    with pytest.raises(HTTPException) as exc_info:
        _validate_csv_upload(file)
    assert exc_info.value.status_code == 400


def test_validate_csv_upload_no_extension():
    file = MagicMock(spec=UploadFile)
    file.filename = "data"
    with pytest.raises(HTTPException) as exc_info:
        _validate_csv_upload(file)
    assert exc_info.value.status_code == 400


def test_validate_csv_upload_empty_filename():
    file = MagicMock(spec=UploadFile)
    file.filename = ""
    with pytest.raises(HTTPException) as exc_info:
        _validate_csv_upload(file)
    assert exc_info.value.status_code == 400


def test_validate_csv_upload_none_filename():
    file = MagicMock(spec=UploadFile)
    file.filename = None
    with pytest.raises(HTTPException) as exc_info:
        _validate_csv_upload(file)
    assert exc_info.value.status_code == 400
