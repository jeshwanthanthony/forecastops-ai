"""Validation and normalization for daily sales CSV files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pandas as pd
import numpy as np


class SalesDataError(ValueError):
    """Raised when a sales file cannot be safely used for forecasting."""


@dataclass(frozen=True)
class DataCleaningReport:
    duplicate_rows_aggregated: int
    missing_days_filled: int


def validate_sales_data(frame: pd.DataFrame) -> tuple[pd.DataFrame, DataCleaningReport]:
    """Return a daily, sorted ``date``/``sales`` frame.

    Required columns are case-insensitive ``date`` and ``sales``. Duplicate dates
    are explicitly aggregated (summed). Missing calendar days are explicitly
    filled by time interpolation, with edge gaps filled from the nearest value.
    This gives the forecasting model a continuous daily series while retaining a
    report for the UI.
    """
    normalized = frame.copy()
    normalized.columns = [str(column).strip().lower() for column in normalized.columns]
    required = {"date", "sales"}
    if not required.issubset(normalized.columns):
        raise SalesDataError("CSV must contain columns named 'date' and 'sales'.")
    if normalized.empty:
        raise SalesDataError("CSV must contain at least one data row.")
    if normalized.columns.duplicated().any():
        raise SalesDataError("CSV column names must be unique.")

    keep = ["date", "sales"] + (["order_count"] if "order_count" in normalized.columns else [])
    normalized = normalized[keep].copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    if normalized["date"].isna().any():
        raise SalesDataError("Every value in the date column must be a valid date.")
    normalized["sales"] = pd.to_numeric(normalized["sales"], errors="coerce")
    if normalized["sales"].isna().any() or not np.isfinite(normalized["sales"]).all():
        raise SalesDataError("Every value in the sales column must be a finite number.")
    if (normalized["sales"] < 0).any():
        raise SalesDataError("Sales values must be nonnegative.")
    if "order_count" in normalized:
        normalized["order_count"] = pd.to_numeric(normalized["order_count"], errors="coerce")
        counts = normalized["order_count"]
        if counts.isna().any() or not np.isfinite(counts).all() or (counts < 0).any() or (counts % 1 != 0).any():
            raise SalesDataError("Optional order_count values must be nonnegative whole numbers.")

    normalized["date"] = normalized["date"].dt.normalize()
    aggregations = {"sales": "sum"}
    if "order_count" in normalized:
        aggregations["order_count"] = "sum"
    daily = normalized.groupby("date", as_index=False, sort=True).agg(aggregations)
    duplicate_rows = int(len(normalized) - len(daily))
    if len(daily) < 28:
        raise SalesDataError("At least 28 distinct daily observations are required for forecasting and backtesting.")
    if (daily["date"].max() - daily["date"].min()).days > 3652:
        raise SalesDataError("CSV date range cannot exceed ten years.")
    full_index = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    daily = daily.set_index("date").reindex(full_index)
    missing_days = int(daily["sales"].isna().sum())
    daily["sales"] = daily["sales"].interpolate(method="time").bfill().ffill()
    if "order_count" in daily:
        daily["order_count"] = daily["order_count"].fillna(0).round().astype(int)
    if len(daily) < 28:
        raise SalesDataError("At least 28 daily observations are required for forecasting and backtesting.")
    daily.index.name = "date"
    return daily.reset_index(), DataCleaningReport(duplicate_rows, missing_days)


def load_sales_csv(source: str | Path | BinaryIO) -> tuple[pd.DataFrame, DataCleaningReport]:
    """Read and validate a CSV file or binary stream."""
    return validate_sales_data(pd.read_csv(source))
