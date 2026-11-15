import io
import json
import re
from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from backend.models import DailyMeasurement, WalkingSession, AppSetting

# Comprehensive column alias dictionary mapping common smartwatch/wearable export names to internal keys
COLUMN_ALIASES: Dict[str, List[str]] = {
    "date": [
        "date", "timestamp", "time", "datetime", "recorded_at", "day",
        "start_time", "start_date", "measurement_date", "reading_date",
        "created_at", "date_time", "record_date", "utc_time", "local_time"
    ],
    "rhr": [
        "resting_hr", "resting_heart_rate", "heart_rate", "hr", "bpm",
        "resting_pulse", "pulse", "resting_hr_bpm", "avg_hr", "mean_hr",
        "heart_rate_bpm", "rhr", "restinghr", "pulse_rate"
    ],
    "hrv": [
        "hrv", "rmssd", "sdnn", "heart_rate_variability", "hrv_rmssd",
        "hrv_ms", "hrv_rmssd_ms", "rmssd_ms", "daily_hrv"
    ],
    "spo2": [
        "spo2", "oxygen", "blood_oxygen", "o2_saturation", "pulse_ox",
        "o2_pct", "oxygen_saturation", "spo2_pct", "blood_oxygen_pct",
        "o2", "oximeter_spo2"
    ],
    "steps": [
        "steps", "step_count", "daily_steps", "total_steps", "step_counts",
        "steps_count", "step"
    ],
    "dist": [
        "distance_km", "distance", "dist", "km", "walk_distance",
        "walking_distance", "total_distance_km", "distance_meters",
        "walking_distance_km", "dist_km", "total_distance"
    ],
    "speed": [
        "walking_speed", "speed", "walk_speed", "pace_kmh", "speed_kmh",
        "speed_km_h", "average_speed", "avg_speed", "walk_speed_kmh",
        "gait_speed", "walking_speed_km_h"
    ],
    "active": [
        "activity_minutes", "active_minutes", "active_time",
        "moderate_to_vigorous_minutes", "duration_minutes", "active_mins",
        "mvpa_minutes", "exercise_minutes", "active_minutes_total", "activity_mins"
    ],
    "sleep": [
        "sleep_hours", "sleep", "total_sleep", "sleep_duration", "asleep_hours",
        "sleep_h", "sleep_hrs", "sleep_duration_hours", "sleep_minutes",
        "time_asleep_hours", "time_in_bed_hours"
    ],
    "sym": [
        "symptom", "symptoms", "sym", "claudication", "pain", "leg_pain",
        "symptom_severity", "severity", "pad_symptom", "calf_pain", "pain_level"
    ],
    "sym_name": [
        "symptom_name", "symptom_type", "sym_name", "description",
        "symptom_desc", "symptom_details", "symptom_notes"
    ],
    "user_id": [
        "user_id", "userid", "patient_id", "patientid", "id", "subject_id"
    ]
}

METRIC_KEYS = ["steps", "dist", "speed", "active", "rhr", "hrv", "spo2", "sleep"]

def clean_column_name(col: str) -> str:
    """Normalize column header: lowercase, remove special characters, trim."""
    return re.sub(r"[^a-z0-9_]+", "", str(col).strip().lower().replace(" ", "_").replace("-", "_"))

def detect_column_mappings(df_cols: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Map input DataFrame columns to internal standard schema.
    Returns:
      mapped: dict internal_name -> original_column_name
      missing_essential: list of required fields missing (e.g. date)
    """
    cleaned_to_orig = {clean_column_name(c): c for c in df_cols}
    mapped = {}

    for internal_key, candidates in COLUMN_ALIASES.items():
        for candidate in candidates:
            cleaned_candidate = clean_column_name(candidate)
            if cleaned_candidate in cleaned_to_orig:
                mapped[internal_key] = cleaned_to_orig[cleaned_candidate]
                break

    missing_essential = []
    if "date" not in mapped:
        missing_essential.append("date (or timestamp/time/datetime)")

    return mapped, missing_essential

def parse_date_string(val: Any) -> Optional[str]:
    """Parse various date/datetime inputs into standardized YYYY-MM-DD string."""
    if pd.isna(val) or val is None or val == "":
        return None
    try:
        if isinstance(val, (datetime, date)):
            return val.strftime("%Y-%m-%d")
        # Try pandas to_datetime
        dt = pd.to_datetime(val)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        # Fallback regex for YYYY-MM-DD
        m = re.search(r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", str(val))
        if m:
            clean = m.group(1).replace("/", "-").replace(".", "-")
            parts = clean.split("-")
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        return None

def process_smartwatch_dataframe(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Takes a raw DataFrame, maps columns, performs data cleaning, physiological
    validation, intraday aggregation, and duplicate tracking.
    """
    if df.empty:
        raise ValueError("The uploaded dataset contains no rows.")

    mapped_cols, missing_essential = detect_column_mappings(df.columns.tolist())
    if missing_essential:
        raise ValueError(
            f"Missing essential date/timestamp column. Found columns: {list(df.columns)}. "
            f"Please ensure your dataset includes at least one date or timestamp column."
        )

    date_col = mapped_cols["date"]
    total_raw_rows = len(df)
    rejected_rows = 0
    rejected_reasons = []

    # Rename mapped columns to internal names
    rename_dict = {orig: key for key, orig in mapped_cols.items()}
    norm_df = df.rename(columns=rename_dict).copy()

    # Normalize dates
    norm_df["clean_date"] = norm_df["date"].apply(parse_date_string)
    invalid_dates = norm_df["clean_date"].isna().sum()
    if invalid_dates > 0:
        rejected_rows += int(invalid_dates)
        rejected_reasons.append(f"{invalid_dates} rows had unparseable date/timestamps.")
        norm_df = norm_df.dropna(subset=["clean_date"])

    if norm_df.empty:
        raise ValueError("Could not extract any valid dates from the uploaded dataset.")

    # Duplicate tracking (identical timestamp + user_id or identical row)
    user_col = "user_id" if "user_id" in norm_df.columns else None
    dup_cols = ["clean_date"]
    if "date" in norm_df.columns:
        dup_cols.append("date")
    if user_col:
        dup_cols.append(user_col)

    duplicate_mask = norm_df.duplicated(subset=dup_cols, keep="first")
    duplicates_detected = int(duplicate_mask.sum())

    # Pre-clean individual metric values
    # Distance conversion: if average distance is > 100, assuming meters -> convert to km
    if "dist" in norm_df.columns:
        norm_df["dist"] = pd.to_numeric(norm_df["dist"], errors="coerce")
        valid_dist = norm_df["dist"].dropna()
        if not valid_dist.empty and valid_dist.median() > 100:
            norm_df["dist"] = norm_df["dist"] / 1000.0

    # Sleep conversion: if average sleep is > 24, assuming minutes -> convert to hours
    if "sleep" in norm_df.columns:
        norm_df["sleep"] = pd.to_numeric(norm_df["sleep"], errors="coerce")
        valid_sleep = norm_df["sleep"].dropna()
        if not valid_sleep.empty and valid_sleep.median() > 24:
            norm_df["sleep"] = norm_df["sleep"] / 60.0

    # SpO2 conversion: if values are between 0.60 and 1.0 (fractional) -> multiply by 100
    if "spo2" in norm_df.columns:
        norm_df["spo2"] = pd.to_numeric(norm_df["spo2"], errors="coerce")
        norm_df.loc[(norm_df["spo2"] > 0.5) & (norm_df["spo2"] <= 1.0), "spo2"] *= 100.0
        # Discard implausible SpO2 (< 60% or > 100%)
        invalid_spo2 = ((norm_df["spo2"] < 60) | (norm_df["spo2"] > 100)).sum()
        if invalid_spo2 > 0:
            rejected_reasons.append(f"{invalid_spo2} implausible SpO2 readings (<60% or >100%) were filtered.")
            norm_df.loc[(norm_df["spo2"] < 60) | (norm_df["spo2"] > 100), "spo2"] = np.nan

    # RHR bounds: 25 - 220 bpm
    if "rhr" in norm_df.columns:
        norm_df["rhr"] = pd.to_numeric(norm_df["rhr"], errors="coerce")
        invalid_rhr = ((norm_df["rhr"] < 25) | (norm_df["rhr"] > 220)).sum()
        if invalid_rhr > 0:
            rejected_reasons.append(f"{invalid_rhr} implausible resting HR readings (<25 or >220 bpm) were filtered.")
            norm_df.loc[(norm_df["rhr"] < 25) | (norm_df["rhr"] > 220), "rhr"] = np.nan

    # Numeric conversion for remaining metrics
    for col in ["steps", "speed", "active", "hrv", "sym"]:
        if col in norm_df.columns:
            norm_df[col] = pd.to_numeric(norm_df[col], errors="coerce")

    # Group by clean_date for intraday aggregation
    aggregated_records: List[Dict[str, Any]] = []
    grouped = norm_df.groupby("clean_date")

    for dt_str, group in grouped:
        rec = {"date": dt_str}

        # Steps: sum across day
        if "steps" in group.columns and group["steps"].notna().any():
            rec["steps"] = int(group["steps"].sum())
        else:
            rec["steps"] = None

        # Distance: sum across day (or max if already cumulative)
        if "dist" in group.columns and group["dist"].notna().any():
            # If multiple records, sum if each is small, else take max
            rec["dist"] = round(float(group["dist"].sum()), 2)
        elif rec["steps"] is not None:
            # Estimate distance from steps if missing (standard stride ~ 0.74m)
            rec["dist"] = round(float(rec["steps"] * 0.00074), 2)
        else:
            rec["dist"] = None

        # Walking speed: mean across valid speeds
        if "speed" in group.columns and group["speed"].notna().any():
            rec["speed"] = round(float(group["speed"].dropna().mean()), 2)
        else:
            rec["speed"] = None

        # Active minutes: sum across day
        if "active" in group.columns and group["active"].notna().any():
            rec["active"] = int(group["active"].sum())
        else:
            rec["active"] = None

        # Resting HR: mean (or 10th percentile for resting estimation)
        if "rhr" in group.columns and group["rhr"].notna().any():
            vals = group["rhr"].dropna().values
            rec["rhr"] = round(float(np.percentile(vals, 10) if len(vals) >= 10 else np.mean(vals)), 1)
        else:
            rec["rhr"] = None

        # HRV: mean
        if "hrv" in group.columns and group["hrv"].notna().any():
            rec["hrv"] = round(float(group["hrv"].dropna().mean()), 1)
        else:
            rec["hrv"] = None

        # SpO2: mean of valid measurements
        if "spo2" in group.columns and group["spo2"].notna().any():
            rec["spo2"] = round(float(group["spo2"].dropna().mean()), 1)
        else:
            rec["spo2"] = None

        # Sleep hours: max or sum
        if "sleep" in group.columns and group["sleep"].notna().any():
            rec["sleep"] = round(float(group["sleep"].dropna().max()), 2)
        else:
            rec["sleep"] = None

        # Symptom severity: max across day
        if "sym" in group.columns and group["sym"].notna().any():
            sym_val = int(group["sym"].dropna().max())
            rec["sym"] = max(0, min(3, sym_val))
        else:
            rec["sym"] = 0

        # Symptom name: most recent or first non-empty
        if "sym_name" in group.columns and group["sym_name"].notna().any():
            rec["symName"] = str(group["sym_name"].dropna().iloc[-1])
        else:
            rec["symName"] = None

        rec["source"] = "import"
        aggregated_records.append(rec)

    # Sort ascending by date
    aggregated_records.sort(key=lambda x: x["date"])

    # Calculate missing recommended columns
    recommended = ["rhr", "spo2", "steps", "dist", "speed", "active", "hrv", "sleep"]
    missing_cols = [c for c in recommended if c not in mapped_cols]

    metadata = {
        "total_raw_rows": total_raw_rows,
        "total_days_extracted": len(aggregated_records),
        "duplicates_detected": duplicates_detected,
        "rejected_rows": rejected_rows,
        "rejected_reasons": rejected_reasons,
        "mapped_columns": mapped_cols,
        "missing_columns": missing_cols,
        "min_date": aggregated_records[0]["date"] if aggregated_records else None,
        "max_date": aggregated_records[-1]["date"] if aggregated_records else None,
    }

    return aggregated_records, metadata

def save_daily_records_to_db(db: Session, records: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Inserts or updates daily records in SQLite database.
    Returns (inserted_count, updated_count).
    """
    inserted = 0
    updated = 0

    for rec in records:
        existing = db.query(DailyMeasurement).filter(DailyMeasurement.date == rec["date"]).first()
        if existing:
            # Update existing record with non-null values
            for k in ["steps", "dist", "speed", "active", "rhr", "hrv", "spo2", "sleep"]:
                if rec.get(k) is not None:
                    setattr(existing, k, rec[k])
            if rec.get("sym") is not None and rec["sym"] > 0:
                existing.sym = rec["sym"]
            if rec.get("symName"):
                existing.sym_name = rec["symName"]
            if rec.get("source"):
                existing.source = rec["source"]
            updated += 1
        else:
            new_record = DailyMeasurement(
                date=rec["date"],
                steps=rec.get("steps"),
                dist=rec.get("dist"),
                speed=rec.get("speed"),
                active=rec.get("active"),
                rhr=rec.get("rhr"),
                hrv=rec.get("hrv"),
                spo2=rec.get("spo2"),
                sleep=rec.get("sleep"),
                sym=rec.get("sym", 0),
                sym_name=rec.get("symName"),
                source=rec.get("source", "import")
            )
            db.add(new_record)
            inserted += 1

    db.commit()
    return inserted, updated

def parse_and_import_smartwatch_file(
    content: bytes,
    filename: str,
    db: Session
) -> Dict[str, Any]:
    """
    High-level handler: parses CSV or JSON bytes, cleans, aggregates,
    persists to SQLite, and returns detailed summary.
    """
    filename_lower = filename.lower()
    df: Optional[pd.DataFrame] = None

    if filename_lower.endswith(".json"):
        try:
            raw_text = content.decode("utf-8-sig", errors="replace")
            json_data = json.loads(raw_text)
            if isinstance(json_data, dict):
                # Check for common wrappers like {"records": [...]}, {"data": [...]}, {"days": [...]}
                for key in ["records", "data", "days", "readings", "items"]:
                    if key in json_data and isinstance(json_data[key], list):
                        json_data = json_data[key]
                        break
            if isinstance(json_data, list):
                df = pd.DataFrame(json_data)
            else:
                raise ValueError("JSON file must contain an array of daily/timestamped records.")
        except Exception as e:
            raise ValueError(f"Failed to parse JSON file: {str(e)}")
    else:
        # Default to CSV / TSV / text
        try:
            raw_text = content.decode("utf-8-sig", errors="replace")
            # Detect separator (comma, semicolon, tab)
            sep = ","
            first_line = raw_text.splitlines()[0] if raw_text.splitlines() else ""
            if "\t" in first_line:
                sep = "\t"
            elif ";" in first_line and "," not in first_line:
                sep = ";"

            df = pd.read_csv(io.StringIO(raw_text), sep=sep)
        except Exception as e:
            raise ValueError(f"Failed to parse CSV file: {str(e)}")

    if df is None or df.empty:
        raise ValueError("Uploaded file contains no data.")

    records, meta = process_smartwatch_dataframe(df)
    inserted, updated = save_daily_records_to_db(db, records)

    return {
        "status": "success",
        "filename": filename,
        "total_rows": meta["total_raw_rows"],
        "imported_days": inserted,
        "updated_days": updated,
        "duplicates_detected": meta["duplicates_detected"],
        "rejected_rows": meta["rejected_rows"],
        "rejected_reasons": meta["rejected_reasons"][:5],  # Cap reasons to 5
        "date_range": {
            "min_date": meta["min_date"],
            "max_date": meta["max_date"]
        },
        "mapped_columns": meta["mapped_columns"],
        "missing_columns": meta["missing_columns"],
        "message": (
            f"Successfully processed {meta['total_raw_rows']} rows. "
            f"Saved {inserted} new day records and updated {updated} existing day records in SQLite."
        )
    }

def calculate_data_quality(days: List[DailyMeasurement]) -> int:
    """
    Computes data quality percentage matching the frontend algorithm:
    Evaluates 30-day completeness, low SpO2 occurrences, and trailing dropouts.
    """
    if not days:
        return 0

    window = days[-30:] if len(days) >= 30 else days
    total_slots = len(window) * len(METRIC_KEYS)
    if total_slots == 0:
        return 0

    filled_slots = 0
    for d in window:
        for k in METRIC_KEYS:
            if getattr(d, k, None) is not None:
                filled_slots += 1

    pct = 100.0 * filled_slots / total_slots

    # Penalty for low SpO2 (< 88%)
    low_spo2_count = sum(1 for d in window if d.spo2 is not None and d.spo2 < 88)
    pct -= low_spo2_count * 3

    # Penalty if last 3 days are completely missing
    if len(days) >= 3:
        last_3 = days[-3:]
        if all(all(getattr(d, k) is None for k in METRIC_KEYS) for d in last_3):
            pct -= 15

    # Small penalty if history is shorter than 30 days
    if len(window) < 30:
        pct -= (30 - len(window)) * 0.8

    return int(max(0, min(100, round(pct))))

def export_database_records(db: Session, export_format: str = "json") -> Tuple[str, str]:
    """
    Exports all daily measurements, walking sessions, and profile settings.
    Returns (content_string, media_type).
    """
    days = db.query(DailyMeasurement).order_by(DailyMeasurement.date.asc()).all()
    walks = db.query(WalkingSession).order_by(WalkingSession.date.asc()).all()
    settings = db.query(AppSetting).all()

    settings_dict = {}
    for s in settings:
        try:
            settings_dict[s.key] = json.loads(s.value)
        except Exception:
            settings_dict[s.key] = s.value

    if export_format.lower() == "csv":
        # Format as CSV with daily measurements
        output = io.StringIO()
        header = ["date"] + METRIC_KEYS + ["sym", "sym_name", "source"]
        output.write(",".join(header) + "\n")
        for d in days:
            row = [
                d.date,
                str(d.steps or ""),
                str(d.dist or ""),
                str(d.speed or ""),
                str(d.active or ""),
                str(d.rhr or ""),
                str(d.hrv or ""),
                str(d.spo2 or ""),
                str(d.sleep or ""),
                str(d.sym or 0),
                f'"{d.sym_name or ""}"',
                d.source or "import"
            ]
            output.write(",".join(row) + "\n")
        return output.getvalue(), "text/csv"
    else:
        # JSON export
        data = {
            "application": "Circulation - PAD Progression Monitor",
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "total_days": len(days),
            "total_walks": len(walks),
            "days": [d.to_dict() for d in days],
            "walks": [w.to_dict() for w in walks],
            "settings": settings_dict
        }
        return json.dumps(data, indent=2), "application/json"
