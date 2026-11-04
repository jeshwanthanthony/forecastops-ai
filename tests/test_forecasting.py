import pandas as pd

from forecasting import chronological_backtest, fit_model, recursive_forecast, seasonal_naive_forecast


def sales_frame(days=70):
    dates = pd.date_range("2025-01-01", periods=days, freq="D")
    values = [100 + (date.dayofweek * 8) + (index % 5) for index, date in enumerate(dates)]
    return pd.DataFrame({"date": dates, "sales": values})


def test_recursive_forecast_has_future_dates_and_nonnegative_sales():
    data = sales_frame()
    forecast = recursive_forecast(fit_model(data), data, 7)
    assert len(forecast) == 7
    assert forecast.date.min() == data.date.max() + pd.Timedelta(1, unit="D")
    assert (forecast.forecast_sales >= 0).all()


def test_backtest_is_chronological_and_reports_both_maes():
    data = sales_frame()
    result = chronological_backtest(data, test_days=14)
    assert result.actual.index.min() > data.date.iloc[:-14].max()
    assert result.model_mae >= 0
    assert result.baseline_mae >= 0


def test_seasonal_naive_repeats_last_week_without_future_actuals():
    data = sales_frame(28)
    forecast = seasonal_naive_forecast(data, 8)
    assert forecast.baseline_sales.iloc[0] == data.sales.iloc[-7]
    assert forecast.baseline_sales.iloc[7] == forecast.baseline_sales.iloc[0]
