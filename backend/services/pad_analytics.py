"""
PAD Analytics and Machine Learning Integration Service (Modular)
Designed for future integration of custom Python PAD analysis models.

Note on Clinical Disclaimer:
All algorithmic estimates are experimental research prototypes and do not
constitute a medical diagnosis or clinical claim.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

def calculate_baseline(days: List[Dict[str, Any]], window_size: Optional[int] = None) -> Dict[str, Any]:
    """
    Computes patient personal baseline (mean and standard deviation)
    over the initial intake window (defaults to first 14-21 days).
    """
    if len(days) < 3:
        return {}

    n = window_size or min(21, max(7, len(days) // 4))
    baseline_slice = days[:n]

    metrics = ["steps", "dist", "speed", "active", "rhr", "hrv", "spo2", "sleep"]
    baseline = {"window_days": n}

    for m in metrics:
        vals = [d[m] for d in baseline_slice if d.get(m) is not None]
        if vals:
            baseline[m] = {
                "mean": round(float(np.mean(vals)), 2),
                "std": round(float(np.std(vals, ddof=1) if len(vals) > 1 else 0.0), 2),
                "count": len(vals)
            }
        else:
            baseline[m] = {"mean": None, "std": None, "count": 0}

    sym_vals = [d.get("sym", 0) for d in baseline_slice]
    baseline["sym"] = round(float(np.mean(sym_vals)), 2) if sym_vals else 0.0

    return baseline

def calculate_linear_trend(values: List[Optional[float]]) -> Optional[Dict[str, float]]:
    """
    Fits ordinary least squares linear regression over valid data points.
    Returns slope (b), intercept (a), and coefficient of determination (r2).
    """
    pairs = [(i, v) for i, v in enumerate(values) if v is not None and not np.isnan(v)]
    if len(pairs) < 3:
        return None

    x = np.array([p[0] for p in pairs])
    y = np.array([p[1] for p in pairs])

    n = len(pairs)
    mx, my = np.mean(x), np.mean(y)

    sxy = np.sum((x - mx) * (y - my))
    sxx = np.sum((x - mx) ** 2)
    syy = np.sum((y - my) ** 2)

    if sxx == 0 or syy == 0:
        return {"b": 0.0, "a": float(my), "r2": 0.0, "n": n}

    b = sxy / sxx
    a = my - b * mx
    r2 = (sxy * sxy) / (sxx * syy)

    return {
        "b": round(float(b), 4),
        "a": round(float(a), 2),
        "r2": round(float(r2), 4),
        "n": n
    }

# Future AI/ML extension hook
class PADModelRegistry:
    """
    Pluggable registry for user-defined machine learning or statistical models.
    Users can register custom PyTorch, scikit-learn, or XGBoost inference pipelines.
    """
    _registered_models = {}

    @classmethod
    def register(cls, model_name: str, model_fn):
        cls._registered_models[model_name] = model_fn

    @classmethod
    def predict(cls, model_name: str, features: Dict[str, Any]) -> Any:
        if model_name not in cls._registered_models:
            raise KeyError(f"Model '{model_name}' is not registered.")
        return cls._registered_models[model_name](features)
