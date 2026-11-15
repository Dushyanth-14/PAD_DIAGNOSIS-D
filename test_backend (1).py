"""
Comprehensive test suite for Circulation - PAD Backend & SQLite Database.
Tests all endpoints: health, status, upload (CSV & JSON), days, walks, settings, export, persistence.
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal, init_db, DATABASE_PATH
from backend.models import DailyMeasurement, WalkingSession, AppSetting

client = TestClient(app)

def test_suite():
    print("=" * 70)
    print("RUNNING CIRCULATION PAD BACKEND & DATABASE TESTS")
    print("=" * 70)

    # 1. Health check
    print("\n[1] Testing GET /api/health...")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    assert health_data["status"] == "healthy"
    print(f" -> Passed! Backend healthy, database: {health_data['database_file']}")

    # 2. Database Status
    print("\n[2] Testing GET /api/status...")
    res = client.get("/api/status")
    assert res.status_code == 200
    status_data = res.json()
    print(f" -> Status: {status_data['status']}, Database file: {status_data['database_file']}, Days: {status_data['total_days']}")

    # 3. CSV Upload with Column Mapping
    print("\n[3] Testing POST /api/upload with smartwatch CSV (custom column names)...")
    csv_path = PROJECT_ROOT / "data" / "sample_smartwatch_data.csv"
    with open(csv_path, "rb") as f:
        res = client.post("/api/upload", files={"file": ("sample_smartwatch_data.csv", f, "text/csv")})
    assert res.status_code == 200, f"CSV upload failed: {res.text}"
    upload_data = res.json()
    assert upload_data["status"] == "success"
    assert upload_data["imported_days"] > 0
    print(f" -> Passed! Processed {upload_data['total_rows']} rows.")
    print(f" -> Imported {upload_data['imported_days']} days, Updated {upload_data['updated_days']} days.")
    print(f" -> Column mappings: {upload_data['mapped_columns']}")

    # 4. Fetch daily records
    print("\n[4] Testing GET /api/days...")
    res = client.get("/api/days")
    assert res.status_code == 200
    days = res.json()
    assert len(days) >= 50, f"Expected at least 50 days, got {len(days)}"
    first_day = days[0]
    print(f" -> Passed! Retrieved {len(days)} stored daily records.")
    print(f" -> Sample record for {first_day['date']}: steps={first_day['steps']}, dist={first_day['dist']}km, rhr={first_day['rhr']}bpm, spo2={first_day['spo2']}%, hrv={first_day['hrv']}ms")

    # 5. Update single day
    print("\n[5] Testing PUT /api/days/{date}...")
    target_date = first_day["date"]
    update_payload = {"steps": 9999, "sym": 2, "symName": "Moderate calf cramps"}
    res = client.put(f"/api/days/{target_date}", json=update_payload)
    assert res.status_code == 200
    updated_day = res.json()
    assert updated_day["steps"] == 9999
    assert updated_day["sym"] == 2
    assert updated_day["symName"] == "Moderate calf cramps"
    print(f" -> Passed! Updated {target_date}: steps={updated_day['steps']}, sym={updated_day['sym']}, symName='{updated_day['symName']}'")

    # 6. Walking sessions: POST and GET
    print("\n[6] Testing POST /api/walks and GET /api/walks...")
    walk_payload = {
        "date": target_date,
        "dur": 6.0,
        "dist": 485.5,
        "avg": 104.0,
        "peak": 128.0,
        "rec": 28.0,
        "spo2": 95.0,
        "notes": "Mild calf discomfort at 4 minutes"
    }
    res = client.post("/api/walks", json=walk_payload)
    assert res.status_code == 201, f"Walk test save failed: {res.text}"
    saved_walk = res.json()
    assert saved_walk["dist"] == 485.5
    assert saved_walk["avg"] == 104.0

    res = client.get("/api/walks")
    assert res.status_code == 200
    walks = res.json()
    assert len(walks) >= 1
    print(f" -> Passed! Saved 6MWT: distance={saved_walk['dist']}m, recovery={saved_walk['rec']}bpm.")
    print(f" -> Total walking sessions in SQLite: {len(walks)}")

    # 7. JSON Upload
    print("\n[7] Testing POST /api/upload with JSON smartwatch data...")
    json_path = PROJECT_ROOT / "data" / "sample_smartwatch_data.json"
    with open(json_path, "rb") as f:
        res = client.post("/api/upload", files={"file": ("sample_smartwatch_data.json", f, "application/json")})
    assert res.status_code == 200, f"JSON upload failed: {res.text}"
    json_summary = res.json()
    assert json_summary["status"] == "success"
    print(f" -> Passed! JSON parsed: {json_summary['imported_days']} new, {json_summary['updated_days']} updated.")

    # 8. Settings & Profile persistence
    print("\n[8] Testing POST /api/settings and GET /api/settings...")
    settings_payload = {
        "profile": {"age": 68, "abi": "0.78", "smoker": True, "diabetes": False, "htn": True, "pad": True},
        "weights": {"activity": 25, "walking": 30, "symptoms": 15, "cardio": 15, "anomaly": 10, "risk": 5}
    }
    res = client.post("/api/settings", json=settings_payload)
    assert res.status_code == 200

    res = client.get("/api/settings")
    assert res.status_code == 200
    loaded_settings = res.json()
    assert loaded_settings["profile"]["age"] == 68
    assert loaded_settings["profile"]["abi"] == "0.78"
    assert loaded_settings["weights"]["walking"] == 30
    print(f" -> Passed! Profile and VFPS weights successfully stored and retrieved.")

    # 9. Export endpoints
    print("\n[9] Testing GET /api/export (CSV & JSON)...")
    res_csv = client.get("/api/export?format=csv")
    assert res_csv.status_code == 200
    assert "date,steps,dist" in res_csv.text

    res_json = client.get("/api/export?format=json")
    assert res_json.status_code == 200
    exp_json = res_json.json()
    assert "days" in exp_json and len(exp_json["days"]) > 0
    print(f" -> Passed! CSV export ({len(res_csv.text)} bytes) and JSON export ({len(exp_json['days'])} days).")

    # 10. Invalid file error handling
    print("\n[10] Testing error handling for invalid datasets...")
    # Missing date column
    invalid_csv = b"foo,bar,baz\n1,2,3\n4,5,6\n"
    res_err = client.post("/api/upload", files={"file": ("bad.csv", invalid_csv, "text/csv")})
    assert res_err.status_code == 422
    assert "Missing essential date/timestamp column" in res_err.json()["detail"]
    print(f" -> Passed! Meaningful error returned: '{res_err.json()['detail'][:60]}...'")

    # 11. Persistence verification (simulating server restart)
    print("\n[11] Verifying SQLite persistence across session restarts...")
    # Open direct independent SQLite session to disk file
    db = SessionLocal()
    try:
        persisted_days_count = db.query(DailyMeasurement).count()
        persisted_walks_count = db.query(WalkingSession).count()
        assert persisted_days_count >= 50
        assert persisted_walks_count >= 1
        print(f" -> Passed! Verified SQLite file {DATABASE_PATH.name} holds {persisted_days_count} days and {persisted_walks_count} walks.")
    finally:
        db.close()

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! BACKEND & DATABASE ARE FULLY FUNCTIONAL.")
    print("=" * 70)

if __name__ == "__main__":
    test_suite()
