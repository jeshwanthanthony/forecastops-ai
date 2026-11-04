import pandas as pd
import pytest

from data_utils import SalesDataError, validate_sales_data


def test_duplicates_are_summed_and_missing_days_are_interpolated():
    frame = pd.DataFrame({"date": ["2025-01-01", "2025-01-01", "2025-01-03"] + [f"2025-01-{day:02d}" for day in range(4, 30)], "sales": [10, 5, 30] + [20] * 26})
    cleaned, report = validate_sales_data(frame)
    assert len(cleaned) == 29
    assert cleaned.loc[cleaned.date == pd.Timestamp("2025-01-01"), "sales"].item() == 15
    assert cleaned.loc[cleaned.date == pd.Timestamp("2025-01-02"), "sales"].item() == 22.5
    assert report.duplicate_rows_aggregated == 1
    assert report.missing_days_filled == 1


@pytest.mark.parametrize("sales", ["not-a-number", -1])
def test_invalid_sales_are_rejected(sales):
    frame = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=21), "sales": [10] * 20 + [sales]})
    with pytest.raises(SalesDataError):
        validate_sales_data(frame)


def test_optional_order_count_is_validated_and_retained():
    frame = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=28), "sales": [10] * 28, "order_count": [2] * 28})
    cleaned, _ = validate_sales_data(frame)
    assert cleaned.order_count.sum() == 56


def test_empty_and_nonfinite_sales_are_rejected():
    with pytest.raises(SalesDataError):
        validate_sales_data(pd.DataFrame(columns=["date", "sales"]))
    with pytest.raises(SalesDataError):
        validate_sales_data(pd.DataFrame({"date": pd.date_range("2025-01-01", periods=28), "sales": [10] * 27 + [float("inf")]}))
