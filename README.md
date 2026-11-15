# Circulation – PAD Progression Monitor

A longitudinal monitoring platform for **Peripheral Artery Disease (PAD)** and lower-extremity vascular functional status, connecting wearable smartwatch measurements to a persistent Python backend, SQLite database, and clinical trends dashboard.

---

## 1. Project Overview

The **Circulation – PAD Progression Monitor** platform tracks long-term wearable metrics to evaluate changes against an individual's personal baseline:
- **Daily Wearable Metrics**: Resting Heart Rate (RHR), Heart Rate Variability (HRV / RMSSD), Pulse Oximetry ($\text{SpO}_2$), Step Counts, Walking Distance, Walking Speed, Active Minutes, and Sleep Duration.
- **Vascular Functional Progression Score (VFPS)**: A normalized multi-component index reflecting functional departures from personal baseline.
- **Linear Trend Forecasting**: 7-day, 30-day, and 90-day trajectory projections.
- **Timed Walk Tests**: 6-Minute Walk Test (6MWT) logging with heart rate recovery and minimum $\text{SpO}_2$.
- **Symptom Tracker**: Claudication and leg pain severity logging.
- **Smartwatch Ingestion**: Intelligent column mapping, physiological range checks, and intraday aggregation for smartwatch CSV and JSON files.
- **Persistent Storage**: SQLite database storing records durably across application restarts.

> **Clinical Disclaimer**: Research prototype. Algorithmic estimates are experimental, not clinically validated, and not a medical diagnosis. Smartwatch data cannot diagnose PAD.

---

## 2. Project Structure

```text
Circulation-PAD/
│
├── frontend/
│   └── index.html               # Enhanced frontend with FastAPI fetch() integration
│
├── backend/
│   ├── main.py                  # FastAPI server with all REST endpoints & static serving
│   ├── database.py              # SQLite connection, WAL mode, session factory
│   ├── models.py                # SQLAlchemy ORM models (daily metrics, walks, settings)
│   ├── schemas.py               # Pydantic validation and serialization schemas
│   ├── requirements.txt         # Python dependencies
│   └── services/
│       ├── __init__.py
│       ├── data_service.py      # Pandas smartwatch ingestion, column mapping & cleaning
│       └── pad_analytics.py     # Modular baseline analysis & future ML model hooks
│
├── data/
│   ├── pad_database.db          # Persistent SQLite database file
│   ├── sample_smartwatch_data.csv   # 60-day sample smartwatch dataset (CSV)
│   └── sample_smartwatch_data.json  # 60-day sample smartwatch dataset (JSON)
│
├── Circulation – PAD Progression Monitor (1).html  # Root synchronized frontend
├── test_backend.py              # Automated test suite verifying all endpoints & DB
└── README.md                    # Setup, execution, and API documentation
```

---

## 3. Windows & VS Code Setup

### Prerequisites
- **Windows 10 or 11**
- **Python 3.9+** (Python 3.11 recommended; verify in terminal with `python --version`)
- **Visual Studio Code** (with Python extension)
- A modern web browser (Google Chrome, Microsoft Edge, or Firefox)

### Step-by-Step Setup

1. **Open the project folder in VS Code**:
   - Launch VS Code.
   - Click **File > Open Folder...** and select the `Circulation-PAD` directory.

2. **Open the Integrated Terminal**:
   - In VS Code, press `Ctrl + \`` (backtick) or select **Terminal > New Terminal**.

3. **(Optional) Create and activate a Virtual Environment**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
   *(If PowerShell displays an execution policy error, run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`)*

4. **Install Dependencies**:
   ```powershell
   pip install -r backend/requirements.txt
   ```

---

## 4. How to Run the Application

### Start the Backend Server

Run the following command from the project root:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
or simply:
```powershell
python backend/main.py
```

Output:
```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

### Open the Application

Once the server is running, you can access the platform in two ways:

1. **Direct Web Browser URL (Recommended)**:
   Navigate to:
   [http://127.0.0.1:8000](http://127.0.0.1:8000)

   *The FastAPI backend automatically serves the frontend at `/`.*

2. **Interactive API Documentation (Swagger UI)**:
   Navigate to:
   [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

3. **Opening HTML directly via file**:
   Double-click `frontend/index.html` or `Circulation – PAD Progression Monitor (1).html`.
   *The frontend auto-detects `file://` execution and connects to `http://127.0.0.1:8000` with full CORS support.*

---

## 5. API Endpoints Reference

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `GET` | `/api/health` | Check backend and SQLite database health |
| `GET` | `/api/status` | SQLite database statistics (record counts, date range, size) |
| `GET` | `/api/days` | Fetch chronological daily wearable measurements |
| `GET` | `/api/days/{date}` | Fetch stored measurements for a single date (`YYYY-MM-DD`) |
| `PUT` | `/api/days/{date}` | Save or update measurements for a specific date |
| `DELETE` | `/api/days/{date}` | Delete a daily record from SQLite |
| `POST` | `/api/days/bulk` | Bulk insert or update daily measurements |
| `GET` | `/api/walks` | Fetch logged 6-minute walk test sessions |
| `POST` | `/api/walks` | Save a new timed walk test session |
| `DELETE` | `/api/walks/{id}` | Delete a walk test session |
| `POST` | `/api/upload` | Upload & process smartwatch CSV or JSON dataset |
| `GET` | `/api/export` | Export database records (`?format=csv` or `?format=json`) |
| `GET` | `/api/settings` | Retrieve user profile risk factors and VFPS weights |
| `POST` | `/api/settings` | Save user profile risk factors and VFPS weights |
| `POST` | `/api/reset` | Clear stored measurements (`?confirm=true`) |

---

## 6. Smartwatch Dataset Ingestion & Column Mapping

The upload endpoint (`POST /api/upload`) uses an intelligent Pandas-based ingestion pipeline in `backend/services/data_service.py` that accommodates diverse export formats:

### Supported Column Aliases

| Standard Field | Common Smartwatch Column Names Mapped Automatically |
|:---|:---|
| **Date / Timestamp** | `timestamp`, `date`, `time`, `datetime`, `recorded_at`, `day`, `start_time`, `created_at` |
| **Resting Heart Rate** | `resting_heart_rate`, `resting_hr`, `heart_rate`, `hr`, `bpm`, `resting_pulse`, `pulse` |
| **Heart Rate Variability** | `heart_rate_variability`, `hrv`, `rmssd`, `hrv_ms`, `rmssd_ms`, `daily_hrv` |
| **$\text{SpO}_2$** | `blood_oxygen`, `spo2`, `oxygen`, `o2_saturation`, `pulse_ox`, `oxygen_saturation` |
| **Step Count** | `step_count`, `steps`, `daily_steps`, `total_steps` |
| **Walking Distance** | `total_distance_km`, `distance_km`, `distance`, `dist`, `km`, `distance_meters` |
| **Walking Speed** | `walk_speed_kmh`, `walking_speed`, `speed`, `pace_kmh`, `speed_km_h`, `avg_speed` |
| **Active Duration** | `duration_minutes`, `activity_minutes`, `active_minutes`, `active_time`, `mvpa_minutes` |
| **Sleep Duration** | `sleep_duration_hours`, `sleep_hours`, `sleep`, `total_sleep`, `sleep_minutes` |
| **Symptoms** | `claudication_symptom`, `symptom`, `symptoms`, `sym`, `claudication`, `pain` |

### Validation & Normalization Rules
1. **Intraday Aggregation**: When a file contains multiple readings per day, steps, distance, and active minutes are summed; resting HR, HRV, $\text{SpO}_2$, and speed are averaged; symptoms take the maximum severity.
2. **Physiological Range Filtering**:
   - $\text{SpO}_2$: Converted from decimal fraction if $\le 1.0$; values $< 60\%$ or $> 100\%$ discarded as sensor artifacts.
   - Resting HR: Bounds enforced between $25$ and $220\text{ bpm}$.
   - Distance: Automatically converted from meters to kilometers if values exceed typical day thresholds.
   - Sleep: Converted from minutes to hours if values $> 24$.
3. **Duplicate Detection**: Identical timestamps or user records are counted and resolved without crashing.
4. **Summary Feedback**: Returns total rows processed, imported count, updated count, duplicates, column mappings, and data quality warnings.

---

## 7. How to Test

An automated end-to-end test suite is included in `test_backend.py`. It tests all endpoints, dataset upload, column mapping, update workflows, walk test logging, settings persistence, export, error handling, and session restart persistence.

Run the test suite:
```powershell
python test_backend.py
```

Expected output:
```text
======================================================================
RUNNING CIRCULATION PAD BACKEND & DATABASE TESTS
======================================================================
[1] Testing GET /api/health... -> Passed!
[2] Testing GET /api/status... -> Passed!
[3] Testing POST /api/upload with smartwatch CSV... -> Passed!
[4] Testing GET /api/days... -> Passed!
[5] Testing PUT /api/days/{date}... -> Passed!
[6] Testing POST /api/walks and GET /api/walks... -> Passed!
[7] Testing POST /api/upload with JSON smartwatch data... -> Passed!
[8] Testing POST /api/settings and GET /api/settings... -> Passed!
[9] Testing GET /api/export (CSV & JSON)... -> Passed!
[10] Testing error handling for invalid datasets... -> Passed!
[11] Verifying SQLite persistence across session restarts... -> Passed!
======================================================================
ALL TESTS PASSED! BACKEND & DATABASE ARE FULLY FUNCTIONAL.
======================================================================
```

---

## 8. Modular Python AI / ML Integration

The backend is structured to allow straightforward integration of future Python machine learning models:
- File: `backend/services/pad_analytics.py`
- Exposes:
  - `calculate_baseline(days, window_size)`
  - `calculate_linear_trend(values)`
  - `PADModelRegistry`: Pluggable registry where custom scikit-learn, PyTorch, or XGBoost inference functions can be hooked into the pipeline.

```python
from backend.services.pad_analytics import PADModelRegistry

# Example: Register a custom progression classifier
def my_custom_pad_model(features):
    # Your trained model inference logic here
    return {"prediction": "moderate_risk", "confidence": 0.88}

PADModelRegistry.register("custom_pad_v1", my_custom_pad_model)
```

---

## 9. Summary of Workflow

1. **Start backend**: `python -m uvicorn backend.main:app --reload`
2. **Open dashboard**: Navigate to `http://127.0.0.1:8000` in your browser.
3. **Upload data**: In the **Wearable Data** tab, click **Import Smartwatch CSV / JSON** and choose your file (or test with `data/sample_smartwatch_data.csv`).
4. **View results**: The dashboard updates with your actual stored measurements from SQLite, displaying VFPS score, 7d/30d/90d forecasts, metric trends, and detected anomalies.
5. **Log walks & symptoms**: Log walk tests and daily symptoms; changes persist directly into `data/pad_database.db`.
6. **Data remains saved**: Close the browser and restart the backend anytime — your data is retained in SQLite.
