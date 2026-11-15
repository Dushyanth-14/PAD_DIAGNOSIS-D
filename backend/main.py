import os
import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import json

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import get_db, init_db, DATABASE_PATH
from backend.models import DailyMeasurement, WalkingSession, AppSetting
from backend.schemas import (
    DailyMeasurementCreate,
    DailyMeasurementUpdate,
    DailyMeasurementResponse,
    BulkDailyImportRequest,
    WalkingSessionCreate,
    WalkingSessionResponse,
    SettingsPayload,
    UploadSummaryResponse,
    DatabaseStatusResponse,
)
from backend.services.data_service import (
    parse_and_import_smartwatch_file,
    save_daily_records_to_db,
    calculate_data_quality,
    export_database_records
)

# Initialize FastAPI application
app = FastAPI(
    title="Circulation – PAD Progression Monitor API",
    description="Backend API and SQLite database for longitudinal Peripheral Artery Disease wearable monitoring.",
    version="1.0.0"
)

# Enable CORS for local development and file:// access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    """Ensure database schema is created on application start without wiping data."""
    init_db()

# ============================================================================
# Core Health & Database Status Endpoints
# ============================================================================

@app.get("/api/health", summary="Check backend status")
def get_health():
    """Returns the operational status of the PAD monitoring backend."""
    return {
        "status": "healthy",
        "app": "Circulation – PAD Progression Monitor",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "database": "sqlite",
        "database_file": str(DATABASE_PATH)
    }

@app.get("/api/status", response_model=DatabaseStatusResponse, summary="Show database statistics")
def get_database_status(db: Session = Depends(get_db)):
    """Provides statistics about persistent SQLite storage, record count, and data quality."""
    total_days = db.query(DailyMeasurement).count()
    total_walks = db.query(WalkingSession).count()

    min_date = db.query(func.min(DailyMeasurement.date)).scalar()
    max_date = db.query(func.max(DailyMeasurement.date)).scalar()

    recent_days = db.query(DailyMeasurement).order_by(DailyMeasurement.date.asc()).all()
    quality_pct = calculate_data_quality(recent_days) if recent_days else None

    # Database file size
    db_size = DATABASE_PATH.stat().st_size if DATABASE_PATH.exists() else 0

    last_record = db.query(DailyMeasurement).order_by(DailyMeasurement.updated_at.desc()).first()
    last_updated = last_record.updated_at.isoformat() if last_record and last_record.updated_at else None

    return {
        "status": "connected",
        "database_file": str(DATABASE_PATH.name),
        "database_size_bytes": db_size,
        "total_days": total_days,
        "total_walks": total_walks,
        "min_date": min_date,
        "max_date": max_date,
        "data_quality_pct": quality_pct,
        "last_updated": last_updated
    }

# ============================================================================
# Daily Measurements Endpoints
# ============================================================================

@app.get("/api/days", response_model=List[DailyMeasurementResponse], summary="Fetch daily wearable measurements")
def get_daily_measurements(
    start_date: Optional[str] = Query(None, description="Filter from YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Filter to YYYY-MM-DD"),
    limit: Optional[int] = Query(None, ge=1, le=5000),
    db: Session = Depends(get_db)
):
    """Retrieves stored daily wearable measurements ordered chronologically."""
    query = db.query(DailyMeasurement)
    if start_date:
        query = query.filter(DailyMeasurement.date >= start_date)
    if end_date:
        query = query.filter(DailyMeasurement.date <= end_date)

    query = query.order_by(DailyMeasurement.date.asc())
    if limit:
        query = query.limit(limit)

    records = query.all()
    return [r.to_dict() for r in records]

@app.get("/api/days/{target_date}", response_model=DailyMeasurementResponse, summary="Get single day measurement")
def get_single_day(target_date: str, db: Session = Depends(get_db)):
    """Fetch stored measurements for a specific date (YYYY-MM-DD)."""
    record = db.query(DailyMeasurement).filter(DailyMeasurement.date == target_date).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"No record found for date {target_date}")
    return record.to_dict()

@app.put("/api/days/{target_date}", response_model=DailyMeasurementResponse, summary="Save or update a day's measurements")
def save_or_update_day(
    target_date: str,
    payload: DailyMeasurementUpdate,
    db: Session = Depends(get_db)
):
    """
    Saves or updates daily wearable metrics (steps, HR, HRV, SpO2, sleep, symptoms).
    Creates a new record if one does not exist for the target date.
    """
    record = db.query(DailyMeasurement).filter(DailyMeasurement.date == target_date).first()
    data = payload.dict(exclude_unset=True)

    if record:
        for k, v in data.items():
            if k == "symName":
                record.sym_name = v
            else:
                setattr(record, k, v)
    else:
        # Create new record
        record = DailyMeasurement(
            date=target_date,
            steps=data.get("steps"),
            dist=data.get("dist"),
            speed=data.get("speed"),
            active=data.get("active"),
            rhr=data.get("rhr"),
            hrv=data.get("hrv"),
            spo2=data.get("spo2"),
            sleep=data.get("sleep"),
            sym=data.get("sym", 0),
            sym_name=data.get("symName"),
            source=data.get("source", "manual")
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return record.to_dict()

@app.delete("/api/days/{target_date}", summary="Delete a day's measurements")
def delete_day(target_date: str, db: Session = Depends(get_db)):
    """Deletes a daily record from SQLite."""
    record = db.query(DailyMeasurement).filter(DailyMeasurement.date == target_date).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"No record found for date {target_date}")
    db.delete(record)
    db.commit()
    return {"status": "deleted", "date": target_date}

@app.post("/api/days/bulk", summary="Import multiple daily records")
def bulk_import_days(
    payload: BulkDailyImportRequest,
    db: Session = Depends(get_db)
):
    """Bulk imports a collection of daily measurements into SQLite with upsert logic."""
    raw_dicts = [d.dict() for d in payload.days]
    inserted, updated = save_daily_records_to_db(db, raw_dicts)
    return {
        "status": "success",
        "inserted": inserted,
        "updated": updated,
        "total_processed": len(raw_dicts)
    }

# ============================================================================
# Walking Sessions Endpoints
# ============================================================================

@app.get("/api/walks", response_model=List[WalkingSessionResponse], summary="Fetch walking session data")
def get_walking_sessions(db: Session = Depends(get_db)):
    """Fetches logged 6-minute walk test sessions, ordered chronologically."""
    sessions = db.query(WalkingSession).order_by(WalkingSession.date.asc()).all()
    return [s.to_dict() for s in sessions]

@app.post("/api/walks", response_model=WalkingSessionResponse, status_code=status.HTTP_201_CREATED, summary="Save a walking session")
def save_walking_session(
    payload: WalkingSessionCreate,
    db: Session = Depends(get_db)
):
    """Saves a new timed walking test session (distance, heart rate recovery, SpO2)."""
    session = WalkingSession(
        date=payload.date,
        dur=payload.dur or 6.0,
        dist=payload.dist,
        avg=payload.avg,
        peak=payload.peak,
        rec=payload.rec,
        spo2=payload.spo2,
        notes=payload.notes
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session.to_dict()

@app.delete("/api/walks/{walk_id}", summary="Delete a walking session")
def delete_walking_session(walk_id: int, db: Session = Depends(get_db)):
    """Deletes a walking test session by ID."""
    session = db.query(WalkingSession).filter(WalkingSession.id == walk_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Walking session not found")
    db.delete(session)
    db.commit()
    return {"status": "deleted", "id": walk_id}

# ============================================================================
# Smartwatch Dataset Upload & Ingestion
# ============================================================================

@app.post("/api/upload", response_model=UploadSummaryResponse, summary="Upload and process smartwatch CSV or JSON data")
async def upload_smartwatch_data(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Accepts smartwatch CSV or JSON export files.
    Performs flexible column mapping, physiological cleaning, intraday aggregation,
    and saves records into persistent SQLite storage.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    allowed_exts = (".csv", ".json", ".txt", ".tsv")
    if not any(file.filename.lower().endswith(ext) for ext in allowed_exts):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{file.filename}'. Please upload a .csv or .json file."
        )

    try:
        content = await file.read()
        summary = parse_and_import_smartwatch_file(content, file.filename, db)
        return summary
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data processing error: {str(e)}")

# ============================================================================
# Export & Settings Endpoints
# ============================================================================

@app.get("/api/export", summary="Export stored measurements")
def export_data(
    format: str = Query("json", regex="^(json|csv)$", description="Export format: 'json' or 'csv'"),
    db: Session = Depends(get_db)
):
    """Exports all stored daily measurements and walks from SQLite."""
    content, media_type = export_database_records(db, export_format=format)
    filename = f"pad_measurements_{datetime.utcnow().strftime('%Y%m%d')}.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/api/settings", summary="Get application settings and profile")
def get_settings(db: Session = Depends(get_db)):
    """Retrieves user profile risk factors and VFPS component weights from SQLite."""
    settings_records = db.query(AppSetting).all()
    res = {
        "profile": {},
        "weights": {
            "activity": 20,
            "walking": 25,
            "symptoms": 20,
            "cardio": 15,
            "anomaly": 10,
            "risk": 10
        }
    }
    for s in settings_records:
        try:
            res[s.key] = json.loads(s.value)
        except Exception:
            res[s.key] = s.value
    return res

@app.post("/api/settings", summary="Save application settings and profile")
def save_settings(
    payload: SettingsPayload,
    db: Session = Depends(get_db)
):
    """Saves user profile risk factors and VFPS weights into SQLite."""
    if payload.profile is not None:
        p_record = db.query(AppSetting).filter(AppSetting.key == "profile").first()
        val = json.dumps(payload.profile.dict())
        if p_record:
            p_record.value = val
        else:
            db.add(AppSetting(key="profile", value=val))

    if payload.weights is not None:
        w_record = db.query(AppSetting).filter(AppSetting.key == "weights").first()
        val = json.dumps(payload.weights.dict())
        if w_record:
            w_record.value = val
        else:
            db.add(AppSetting(key="weights", value=val))

    db.commit()
    return {"status": "saved"}

@app.post("/api/reset", summary="Reset database records")
def reset_database(
    confirm: bool = Query(False, description="Set confirm=true to wipe daily measurements and walks"),
    db: Session = Depends(get_db)
):
    """Utility endpoint to clear stored measurements (e.g. for testing new datasets)."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Pass ?confirm=true to reset measurements."
        )
    db.query(DailyMeasurement).delete()
    db.query(WalkingSession).delete()
    db.commit()
    return {"status": "reset", "message": "Daily measurements and walk sessions cleared."}

# ============================================================================
# Static Files & Frontend Serving
# ============================================================================

FRONTEND_INDEX = PROJECT_ROOT / "frontend" / "index.html"
LEGACY_INDEX = PROJECT_ROOT / "Circulation – PAD Progression Monitor (1).html"

@app.get("/", response_class=FileResponse, summary="Serve frontend application")
def serve_frontend_root():
    """Serves the Circulation PAD frontend web application directly."""
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    if LEGACY_INDEX.exists():
        return FileResponse(LEGACY_INDEX)
    return PlainTextResponse("Circulation PAD Backend Running. Frontend file not found.", status_code=404)

# Mount frontend directory for assets if needed
frontend_dir = PROJECT_ROOT / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

if __name__ == "__main__":
    import uvicorn
    print("=" * 70)
    print("Starting Circulation – PAD Progression Monitor Backend...")
    print(f"Database Path : {DATABASE_PATH}")
    print("Server URL    : http://127.0.0.1:8000")
    print("API Docs      : http://127.0.0.1:8000/docs")
    print("=" * 70)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
