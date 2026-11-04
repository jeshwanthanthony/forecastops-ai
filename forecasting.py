"""Small, leakage-safe daily sales forecasting helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

LAGS = (1, 7, 14)


@dataclass(frozen=True)
class BacktestResult:
    model_mae: float
    baseline_mae: float
    actual: pd.Series
    model_predictions: pd.Series
    baseline_predictions: pd.Series


def _features(date: pd.Timestamp, history: list[float]) -> dict[str, float]:
    """Features available at prediction time only."""
    return {
        "day_of_week": float(date.dayofweek),
        "month": float(date.month),
        "day_of_year_sin": float(np.sin(2 * np.pi * date.dayofyear / 365.25)),
        "day_of_year_cos": float(np.cos(2 * np.pi * date.dayofyear / 365.25)),
        **{f"lag_{lag}": float(history[-lag]) for lag in LAGS},
    }


def _training_frame(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    values = data["sales"].astype(float).tolist()
    rows, targets = [], []
    for index in range(max(LAGS), len(data)):
        rows.append(_features(pd.Timestamp(data["date"].iloc[index]), values[:index]))
        targets.append(values[index])
    return pd.DataFrame(rows), pd.Series(targets)


def fit_model(train: pd.DataFrame) -> RandomForestRegressor:
    """Fit a deterministic, compact regression model on historical rows only."""
    if len(train) < max(LAGS) + 7:
        raise ValueError("At least 21 daily observations are required for forecasting.")
    features, target = _training_frame(train)
    model = RandomForestRegressor(
        n_estimators=150, min_samples_leaf=2, random_state=42, n_jobs=-1
    )
    model.fit(features, target)
    return model


def recursive_forecast(model: RandomForestRegressor, history: pd.DataFrame, days: int) -> pd.DataFrame:
    """Forecast forward without reading any future actual sales values."""
    if days < 1:
        raise ValueError("days must be positive")
    values = history["sales"].astype(float).tolist()
    start = pd.Timestamp(history["date"].iloc[-1]) + pd.Timedelta(1, unit="D")
    dates, predictions = [], []
    for offset in range(days):
        date = start + pd.Timedelta(offset, unit="D")
        prediction = max(0.0, float(model.predict(pd.DataFrame([_features(date, values)]))[0]))
        dates.append(date)
        predictions.append(prediction)
        values.append(prediction)  # future lags use predictions, never hidden actuals
    return pd.DataFrame({"date": dates, "forecast_sales": predictions})


def seasonal_naive_forecast(history: pd.DataFrame, days: int) -> pd.DataFrame:
    """Seven-day seasonal naive baseline, recursively repeated beyond one week."""
    values = history["sales"].astype(float).tolist()
    if len(values) < 7:
        raise ValueError("Seasonal naive forecasting needs at least seven rows.")
    dates, predictions = [], []
    start = pd.Timestamp(history["date"].iloc[-1]) + pd.Timedelta(1, unit="D")
    for offset in range(days):
        prediction = float(values[-7])
        values.append(prediction)
        dates.append(start + pd.Timedelta(offset, unit="D"))
        predictions.append(prediction)
    return pd.DataFrame({"date": dates, "baseline_sales": predictions})


def chronological_backtest(data: pd.DataFrame, test_days: int = 28) -> BacktestResult:
    """Hold out the latest observations and recursively predict them from the past."""
    if len(data) < max(LAGS) + 14:
        raise ValueError("At least 28 daily observations are required for backtesting.")
    horizon = min(test_days, max(7, len(data) // 4))
    train, test = data.iloc[:-horizon].copy(), data.iloc[-horizon:].copy()
    model = fit_model(train)
    model_forecast = recursive_forecast(model, train, horizon)
    baseline_forecast = seasonal_naive_forecast(train, horizon)
    actual = test.set_index("date")["sales"]
    model_predictions = model_forecast.set_index("date")["forecast_sales"]
    baseline_predictions = baseline_forecast.set_index("date")["baseline_sales"]
    return BacktestResult(
        model_mae=float(mean_absolute_error(actual, model_predictions)),
        baseline_mae=float(mean_absolute_error(actual, baseline_predictions)),
        actual=actual,
        model_predictions=model_predictions,
        baseline_predictions=baseline_predictions,
    )
