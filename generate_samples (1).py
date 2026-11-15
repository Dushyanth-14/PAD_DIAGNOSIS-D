import csv
import json
from datetime import datetime, timedelta
import random

random.seed(42)

# Generate 60 days of realistic smartwatch data
start_date = datetime.now() - timedelta(days=60)
csv_rows = []
json_records = []

for i in range(60):
    dt = start_date + timedelta(days=i)
    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")

    # Gradual slight decline for PAD scenario
    factor = 1.0 - (i / 60.0) * 0.15

    steps = int(8500 * factor + random.gauss(0, 400))
    dist_km = round(steps * 0.00074, 2)
    speed_kmh = round(4.5 * factor + random.gauss(0, 0.15), 2)
    active_mins = int(50 * factor + random.gauss(0, 5))
    resting_hr = round(64.0 + (1.0 - factor) * 8.0 + random.gauss(0, 1.5), 1)
    hrv_ms = round(52.0 * factor + random.gauss(0, 3.0), 1)
    spo2 = round(min(100.0, max(91.0, 97.0 - (1.0 - factor) * 3.0 + random.gauss(0, 0.6))), 1)
    sleep_hrs = round(7.2 + random.gauss(0, 0.4), 2)
    sym = 1 if i > 35 and random.random() < 0.35 else (2 if i > 50 and random.random() < 0.25 else 0)

    row = {
        "timestamp": date_str,
        "resting_heart_rate": resting_hr,
        "heart_rate_variability": hrv_ms,
        "blood_oxygen": spo2,
        "step_count": steps,
        "total_distance_km": dist_km,
        "walk_speed_kmh": speed_kmh,
        "duration_minutes": active_mins,
        "sleep_duration_hours": sleep_hrs,
        "claudication_symptom": sym
    }
    csv_rows.append(row)
    json_records.append(row)

# Save sample CSV
with open("data/sample_smartwatch_data.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
    writer.writeheader()
    writer.writerows(csv_rows)

# Save sample JSON
with open("data/sample_smartwatch_data.json", "w", encoding="utf-8") as f:
    json.dump({"records": json_records}, f, indent=2)

print("Generated data/sample_smartwatch_data.csv and data/sample_smartwatch_data.json")
