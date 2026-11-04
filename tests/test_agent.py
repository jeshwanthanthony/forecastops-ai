import pandas as pd
import pytest

from agent import answer_sales_question, get_forecast, get_sales_summary


def sample_data():
    dates = pd.date_range("2025-01-01", periods=30, freq="D")
    return pd.DataFrame({"date": dates, "sales": [100 + (day.dayofweek * 10) for day in dates]})


def test_agent_tools_return_values_from_the_supplied_dataset():
    data = sample_data()
    summary = get_sales_summary(data)
    forecast = get_forecast(data, 7)
    assert summary["total_sales"] == float(data.sales.sum())
    assert len(forecast) == 7
    assert forecast[0]["date"] == "2025-01-31"


def test_agent_requires_a_key_instead_of_fabricating_an_answer(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        answer_sales_question("What are sales?", sample_data())
