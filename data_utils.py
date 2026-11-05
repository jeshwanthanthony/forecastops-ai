"""Validation and normalization for daily sales CSV files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
import csv
import io
import re

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


DATE_NAMES = {"date", "transaction_date", "order_date", "business_date", "timestamp"}
SALES_NAMES = {"sales", "revenue", "total", "amount", "net_sales", "gross_sales"}
COUNT_NAMES = {"order_count", "orders", "transaction_count"}


def read_business_csv(payload: bytes) -> tuple[pd.DataFrame, dict]:
    if not payload:
        raise SalesDataError("The CSV file is empty.")
    if len(payload) > 5 * 1024 * 1024:
        raise SalesDataError("File exceeds the 5 MB limit.")
    try:
        text = payload.decode("utf-8-sig")
        encoding = "utf-8"
    except UnicodeDecodeError:
        text = payload.decode("cp1252")
        encoding = "windows-1252"
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        delimiter = dialect.delimiter
        frame = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False, nrows=100001)
    except (csv.Error, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise SalesDataError("Unable to read the CSV. Check its delimiter and headers.") from error
    if frame.empty or len(frame.columns) > 100:
        raise SalesDataError("CSV must contain data and no more than 100 columns.")
    if len(frame) > 100000:
        raise SalesDataError("CSV cannot contain more than 100,000 rows.")
    def matches(names):
        return [c for c in frame.columns if re.sub(r"[\s-]+", "_", c.strip().lower()) in names]
    candidates = {"date": matches(DATE_NAMES), "sales": matches(SALES_NAMES), "order_count": matches(COUNT_NAMES)}
    return frame, {"encoding": encoding, "delimiter": {",": "comma", ";": "semicolon", "\t": "tab"}[delimiter], "columns": list(frame.columns), "candidates": candidates, "preview": frame.head(5).to_dict(orient="records")}


def normalize_business_csv(frame: pd.DataFrame, date_column: str, sales_column: str, count_column: str = "", date_order: str = ""):
    if date_column not in frame or sales_column not in frame or date_column == sales_column:
        raise SalesDataError("Choose distinct date and sales columns.")
    if count_column and (count_column not in frame or count_column in (date_column, sales_column)):
        raise SalesDataError("Choose a distinct order-count column.")
    raw_dates = frame[date_column].str.strip()
    ambiguous = raw_dates.str.match(r"^\d{1,2}/\d{1,2}/\d{4}(?:\s|$)")
    if ambiguous.any() and date_order not in ("mdy", "dmy"):
        raise SalesDataError("Ambiguous date format. Choose month/day/year or day/month/year.")
    dates = pd.to_datetime(raw_dates, errors="coerce", format="mixed", dayfirst=date_order == "dmy", utc=True)
    if dates.isna().any():
        raise SalesDataError("Date column contains invalid values.")
    amounts = frame[sales_column].str.strip().str.replace(r"[$£€\s,]", "", regex=True)
    amounts = amounts.str.replace(r"^\((.+)\)$", r"-\1", regex=True)
    numeric = pd.to_numeric(amounts, errors="coerce")
    if numeric.isna().any() or not np.isfinite(numeric).all():
        raise SalesDataError("Sales column contains invalid values.")
    data = pd.DataFrame({"date": dates.dt.tz_localize(None).dt.normalize(), "sales": numeric})
    if count_column:
        counts = pd.to_numeric(frame[count_column], errors="coerce")
        if counts.isna().any() or (counts < 0).any() or (counts % 1 != 0).any():
            raise SalesDataError("Order counts must be nonnegative whole numbers.")
        data["order_count"] = counts
    grouped = data.groupby("date", as_index=False).sum(numeric_only=True)
    if (grouped.sales < 0).any():
        raise SalesDataError("Daily net sales cannot be negative; review refund rows.")
    if len(grouped) < 28:
        raise SalesDataError("At least 28 distinct daily observations are required.")
    if (grouped.date.max() - grouped.date.min()).days > 3652:
        raise SalesDataError("CSV date range cannot exceed ten years.")
    full = pd.date_range(grouped.date.min(), grouped.date.max())
    missing = len(full) - len(grouped)
    result = grouped.set_index("date").reindex(full, fill_value=0).rename_axis("date").reset_index()
    return result, {"input_rows": len(frame), "duplicate_rows_aggregated": len(frame) - len(grouped), "missing_days_filled": missing, "invalid_rows": 0, "sales_column": sales_column}
