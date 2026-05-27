import pandas as pd
from unittest.mock import MagicMock, patch
import pytest
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.services.analytics import _json_safe, _numeric_stats, analyze_csv_file, process_uploaded_csv


def test_json_safe_nan():
    assert _json_safe(float("nan")) is None

def test_json_safe_normal():
    assert _json_safe(5) == 5

def test_numeric_stats():
    df = pd.DataFrame({
        "sales": [10, 20, 30],
        "cost": [1, 2, 3]
    })

    result = _numeric_stats(df)

    assert result["sales"]["sum"] == 60
    assert result["sales"]["average"] == 20
    assert result["sales"]["min"] == 10
    assert result["sales"]["max"] == 30

def test_analyze_csv_file(tmp_path):
    csv_file = tmp_path / "data.csv"

    csv_file.write_text(
        "name,sales\n"
        "A,100\n"
        "B,200\n"
    )

    result = analyze_csv_file(csv_file)

    assert result["row_count"] == 2
    assert result["column_count"] == 2
    assert "sales" in result["columns"]

    stats = result["numeric_statistics"]

    assert stats["sales"]["sum"] == 300

def test_analyze_csv_missing_values(tmp_path):
    csv_file = tmp_path / "missing.csv"

    csv_file.write_text(
        "name,sales\n"
        "A,100\n"
        "B,\n"
    )

    result = analyze_csv_file(csv_file)

    missing = result["missing_values"]

    assert missing["sales"] == 1

def test_process_uploaded_csv_not_found():
    db = MagicMock()

    db.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(ValueError):
        process_uploaded_csv(
            db,
            owner_id=1,
            upload_id="missing"
        )

def test_process_uploaded_csv_success(tmp_path):
    csv_file = tmp_path / "sales.csv"

    csv_file.write_text(
        "sales\n"
        "100\n"
        "200\n"
    )

    fake_upload = MagicMock()
    fake_upload.id = "1"
    fake_upload.original_filename = "sales.csv"
    fake_upload.size_bytes = 100
    fake_upload.storage_path = str(csv_file)

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = fake_upload

    result = process_uploaded_csv(
        db,
        owner_id=1,
        upload_id="1"
    )

    assert result["upload"]["filename"] == "sales.csv"

    analytics = result["analytics"]

    assert analytics["row_count"] == 2