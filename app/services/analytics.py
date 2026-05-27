from pathlib import Path
from typing import Any
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import UploadedFile

def _json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value

def _numeric_stats(data_frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    numeric_frame = data_frame.select_dtypes(include="number")
    stats: dict[str, dict[str, Any]] = {}

    for column_name in numeric_frame.columns:
        series = numeric_frame[column_name]
        stats[str(column_name)] = {
            "count": int(series.count()),
            "missing": int(series.isna().sum()),
            "sum": _json_safe(series.sum()),
            "average": _json_safe(series.mean()),
            "min": _json_safe(series.min()),
            "max": _json_safe(series.max()),
        }

    return stats

def analyze_csv_file(file_path: Path) -> dict[str, Any]:
    data_frame = pd.read_csv(file_path)

    column_stats: dict[str, dict[str, Any]] = {}
    for column_name in data_frame.columns:
        series = data_frame[column_name]
        column_stats[str(column_name)] = {
            "dtype": str(series.dtype),
            "non_null_count": int(series.count()),
            "missing_count": int(series.isna().sum()),
            "missing_percent": round(float(series.isna().mean() * 100), 2),
            "unique_count": int(series.nunique(dropna=True)),
        }

    return {
        "row_count": int(len(data_frame)),
        "column_count": int(len(data_frame.columns)),
        "columns": [str(column) for column in data_frame.columns],
        "missing_values": {
            str(column): int(data_frame[column].isna().sum())
            for column in data_frame.columns
        },
        "column_statistics": column_stats,
        "numeric_statistics": _numeric_stats(data_frame),
    }

def process_uploaded_csv(db: Session, *, owner_id: int, upload_id: str) -> dict[str, Any]:
    uploaded_file = db.execute(
        select(UploadedFile).where(
            UploadedFile.id == upload_id,
            UploadedFile.owner_id == owner_id,
        )
    ).scalar_one_or_none()

    if uploaded_file is None:
        raise ValueError("Uploaded CSV file not found")

    file_path = Path(uploaded_file.storage_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Uploaded CSV file is missing from storage: {file_path}")

    analytics = analyze_csv_file(file_path)
    return {
        "upload": {
            "id": uploaded_file.id,
            "filename": uploaded_file.original_filename,
            "size_bytes": uploaded_file.size_bytes,
        },
        "analytics": analytics,
    }
