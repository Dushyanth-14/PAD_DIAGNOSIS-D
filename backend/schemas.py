from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DailyMeasurementBase(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date in YYYY-MM-DD format")
    steps: Optional[int] = Field(None, ge=0, le=200000)
    dist: Optional[float] = Field(None, ge=0.0, le=200.0, description="Walking distance in km")
    speed: Optional[float] = Field(None, ge=0.0, le=50.0, description="Walking speed in km/h")
    active: Optional[int] = Field(None, ge=0, le=1440, description="Active minutes")
    rhr: Optional[float] = Field(None, ge=20.0, le=250.0, description="Resting HR in bpm")
    hrv: Optional[float] = Field(None, ge=1.0, le=500.0, description="HRV (RMSSD) in ms")
    spo2: Optional[float] = Field(None, ge=60.0, le=100.0, description="SpO2 percentage")
    sleep: Optional[float] = Field(None, ge=0.0, le=24.0, description="Sleep in hours")
    sym: Optional[int] = Field(0, ge=0, le=3, description="Symptom severity (0=none, 1=mild, 2=mod, 3=severe)")
    symName: Optional[str] = Field(None, description="Symptom name or description")
    source: Optional[str] = Field("import", description="Data origin: import, manual, live, demo")

class DailyMeasurementCreate(DailyMeasurementBase):
    pass

class DailyMeasurementUpdate(BaseModel):
    steps: Optional[int] = Field(None, ge=0, le=200000)
    dist: Optional[float] = Field(None, ge=0.0, le=200.0)
    speed: Optional[float] = Field(None, ge=0.0, le=50.0)
    active: Optional[int] = Field(None, ge=0, le=1440)
    rhr: Optional[float] = Field(None, ge=20.0, le=250.0)
    hrv: Optional[float] = Field(None, ge=1.0, le=500.0)
    spo2: Optional[float] = Field(None, ge=60.0, le=100.0)
    sleep: Optional[float] = Field(None, ge=0.0, le=24.0)
    sym: Optional[int] = Field(None, ge=0, le=3)
    symName: Optional[str] = None
    source: Optional[str] = None

class DailyMeasurementResponse(DailyMeasurementBase):
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True

class BulkDailyImportRequest(BaseModel):
    days: List[DailyMeasurementCreate]
    overwrite: bool = True

class WalkingSessionCreate(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    dur: Optional[float] = Field(6.0, ge=0.5, le=60.0, description="Duration in minutes")
    dist: float = Field(..., ge=0.0, le=10000.0, description="Distance walked in meters")
    avg: Optional[float] = Field(None, ge=30.0, le=240.0, description="Average HR in bpm")
    peak: Optional[float] = Field(None, ge=30.0, le=250.0, description="Peak HR in bpm")
    rec: Optional[float] = Field(None, ge=0.0, le=120.0, description="1-minute HR recovery in bpm")
    spo2: Optional[float] = Field(None, ge=60.0, le=100.0, description="Minimum SpO2 during walk in %")
    notes: Optional[str] = None

class WalkingSessionResponse(WalkingSessionCreate):
    id: Optional[int] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

class ProfileSchema(BaseModel):
    age: Optional[int] = Field(None, ge=18, le=120)
    abi: Optional[str] = None
    smoker: Optional[bool] = False
    diabetes: Optional[bool] = False
    htn: Optional[bool] = False
    pad: Optional[bool] = False

class WeightsSchema(BaseModel):
    activity: Optional[float] = 20.0
    walking: Optional[float] = 25.0
    symptoms: Optional[float] = 20.0
    cardio: Optional[float] = 15.0
    anomaly: Optional[float] = 10.0
    risk: Optional[float] = 10.0

class SettingsPayload(BaseModel):
    profile: Optional[ProfileSchema] = None
    weights: Optional[WeightsSchema] = None

class UploadSummaryResponse(BaseModel):
    status: str
    filename: str
    total_rows: int
    imported_days: int
    updated_days: int
    duplicates_detected: int
    rejected_rows: int
    rejected_reasons: List[str]
    date_range: Optional[Dict[str, Optional[str]]] = None
    mapped_columns: Dict[str, str]
    missing_columns: List[str]
    message: str

class DatabaseStatusResponse(BaseModel):
    status: str
    database_file: str
    database_size_bytes: int
    total_days: int
    total_walks: int
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    data_quality_pct: Optional[int] = None
    last_updated: Optional[str] = None
