"""
routers/data.py - CSV file management endpoints.

Routes
------
POST /data/upload  - Upload a Dukascopy or HistData CSV file.
GET  /data/files   - List uploaded CSV files.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from algo_trading.data_feed.data_feed import detect_timeframe_from_df, load_csv
from api.schemas.backtest import DataFileInfo

router = APIRouter(prefix="/data", tags=["data"])

DATA_RAW_DIR = Path("data/raw")


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=DataFileInfo,
    summary="Upload a CSV file",
    description=(
        "Upload a Dukascopy or HistData.com MetaTrader CSV export. "
        "The format is auto-detected. The file is parsed to extract bar count "
        "and date range, and a sidecar metadata JSON file is written alongside it."
    ),
)
async def upload_csv(
    symbol: str = Query(..., description="Instrument symbol, e.g. XAUUSD"),
    timeframe: str = Query(default="H1", description="Hint only — actual timeframe is auto-detected from bar spacing."),
    file: UploadFile = File(...),
) -> DataFileInfo:
    """Accept a CSV upload (Dukascopy or HistData format), persist it, and return file metadata."""
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    csv_path = DATA_RAW_DIR / f"{file_id}.csv"
    meta_path = DATA_RAW_DIR / f"{file_id}.meta.json"

    # Write the uploaded bytes to disk
    content = await file.read()
    csv_path.write_bytes(content)

    # Parse the CSV to extract bar count and date range (auto-detect format)
    try:
        df = load_csv(str(csv_path), symbol)
    except Exception as exc:
        csv_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse CSV: {exc}",
        ) from exc

    # Auto-detect the actual timeframe from bar intervals; ignore the hint param
    detected_timeframe = detect_timeframe_from_df(df)

    uploaded_at = datetime.now(tz=timezone.utc).isoformat()
    date_from = df.index[0].isoformat()
    date_to = df.index[-1].isoformat()
    bars = len(df)
    original_filename = file.filename or f"{symbol}_{detected_timeframe}.csv"

    meta = {
        "file_id": file_id,
        "filename": original_filename,
        "symbol": symbol,
        "timeframe": detected_timeframe,
        "bars": bars,
        "date_from": date_from,
        "date_to": date_to,
        "uploaded_at": uploaded_at,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return DataFileInfo(**meta)


@router.get(
    "/files",
    response_model=list[DataFileInfo],
    summary="List uploaded CSV files",
    description="Return metadata for all previously uploaded Dukascopy CSV files, newest first.",
)
async def list_files() -> list[DataFileInfo]:
    """Scan data/raw for sidecar JSON files and return the list sorted newest first."""
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

    results: list[DataFileInfo] = []
    for meta_path in DATA_RAW_DIR.glob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            results.append(DataFileInfo(**meta))
        except Exception:
            # Skip malformed sidecar files silently
            continue

    # Sort newest uploaded_at first
    results.sort(key=lambda f: f.uploaded_at, reverse=True)
    return results


@router.delete(
    "/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an uploaded CSV file",
    description=(
        "Permanently delete a previously uploaded Dukascopy CSV file "
        "and its sidecar metadata. This does not delete any backtest runs "
        "that used this file."
    ),
)
async def delete_file(file_id: str) -> None:
    """Delete the CSV and its sidecar JSON for the given file_id."""
    csv_path  = DATA_RAW_DIR / f"{file_id}.csv"
    meta_path = DATA_RAW_DIR / f"{file_id}.meta.json"

    if not csv_path.exists() and not meta_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_id}",
        )

    csv_path.unlink(missing_ok=True)
    meta_path.unlink(missing_ok=True)
