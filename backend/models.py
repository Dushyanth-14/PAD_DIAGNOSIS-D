from sqlalchemy import Column, Integer, Float, String, Text, DateTime, func, UniqueConstraint
from backend.database import Base

class DailyMeasurement(Base):
    """
    Stores daily aggregated wearable and symptom measurements for PAD monitoring.
    Key metrics align with the frontend M definition:
    - steps, dist (km), speed (km/h), active (mins)
    - rhr (bpm), hrv (ms), spo2 (%), sleep (hours), sym (0-3 severity)
    """
    __tablename__ = "daily_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), unique=True, index=True, nullable=False)  # Format: YYYY-MM-DD
    steps = Column(Integer, nullable=True)
    dist = Column(Float, nullable=True)     # Distance in km
    speed = Column(Float, nullable=True)    # Walking speed in km/h
    active = Column(Integer, nullable=True) # Active minutes
    rhr = Column(Float, nullable=True)      # Resting Heart Rate in bpm
    hrv = Column(Float, nullable=True)      # Heart Rate Variability in ms (RMSSD)
    spo2 = Column(Float, nullable=True)     # Oxygen saturation in %
    sleep = Column(Float, nullable=True)    # Sleep duration in hours
    sym = Column(Integer, default=0)        # Symptom severity: 0=none, 1=mild, 2=mod, 3=severe
    sym_name = Column(String(255), nullable=True) # Symptom description
    source = Column(String(50), default="import")  # 'import', 'live', 'manual', 'demo'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "steps": self.steps,
            "dist": round(self.dist, 2) if self.dist is not None else None,
            "speed": round(self.speed, 2) if self.speed is not None else None,
            "active": self.active,
            "rhr": round(self.rhr, 1) if self.rhr is not None else None,
            "hrv": round(self.hrv, 1) if self.hrv is not None else None,
            "spo2": round(self.spo2, 1) if self.spo2 is not None else None,
            "sleep": round(self.sleep, 2) if self.sleep is not None else None,
            "sym": self.sym or 0,
            "symName": self.sym_name,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WalkingSession(Base):
    """
    Stores 6-minute walk test results (clinical or self-timed).
    Used for exercise response and claudication distance progression.
    """
    __tablename__ = "walking_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), index=True, nullable=False)  # YYYY-MM-DD
    dur = Column(Float, default=6.0)                       # Duration in minutes
    dist = Column(Float, nullable=False)                   # Distance in meters
    avg = Column(Float, nullable=True)                     # Avg HR during walk (bpm)
    peak = Column(Float, nullable=True)                    # Peak HR (bpm)
    rec = Column(Float, nullable=True)                     # HR recovery after 1 min (bpm)
    spo2 = Column(Float, nullable=True)                    # Minimum SpO2 during walk (%)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "dur": self.dur,
            "dist": round(self.dist, 1) if self.dist is not None else None,
            "avg": round(self.avg, 1) if self.avg is not None else None,
            "peak": round(self.peak, 1) if self.peak is not None else None,
            "rec": round(self.rec, 1) if self.rec is not None else None,
            "spo2": round(self.spo2, 1) if self.spo2 is not None else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AppSetting(Base):
    """
    Stores persistent application configurations, user profile (ABI, risk factors),
    and VFPS weight preferences.
    """
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)  # Stored as JSON string
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
