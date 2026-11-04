"""Optional OpenAI Responses API assistant backed only by dashboard data."""

from __future__ import annotations

import json
import os

import pandas as pd

from forecasting import fit_model, recursive_forecast


def get_sales_summary(data: pd.DataFrame) -> dict[str, object]:
    """Return summary figures computed from the supplied, validated dataset."""
    sales = data["sales"]
    return {
        "start_date": str(data["date"].min().date()),
        "end_date": str(data["date"].max().date()),
        "days": int(len(data)),
        "total_sales": round(float(sales.sum()), 2),
        "average_daily_sales": round(float(sales.mean()), 2),
        "latest_daily_sales": round(float(sales.iloc[-1]), 2),
    }


def get_forecast(data: pd.DataFrame, days: int = 7) -> list[dict[str, object]]:
    """Return forecasts computed from supplied data; never invents sales values."""
    days = max(1, min(int(days), 30))
    forecast = recursive_forecast(fit_model(data), data, days)
    return [
        {"date": str(row.date.date()), "forecast_sales": round(float(row.forecast_sales), 2)}
        for row in forecast.itertuples(index=False)
    ]


TOOLS = [
    {
        "type": "function",
        "name": "get_sales_summary",
        "description": "Get factual summary statistics from the loaded sales data.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_forecast",
        "description": "Get a real forecast from the loaded sales data for 1 to 30 days.",
        "parameters": {
            "type": "object",
            "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 30}},
            "required": ["days"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def answer_sales_question(question: str, data: pd.DataFrame) -> str:
    """Use real OpenAI function calls when configured; otherwise raise a clear error."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in .env to enable the assistant.")
    from openai import OpenAI

    client = OpenAI()
    messages: list[object] = [{"role": "user", "content": question}]
    instructions = (
        "You are a sales-data assistant. For every numerical claim about sales or "
        "forecasts, call a supplied tool first and use only its returned values. "
        "Never invent numbers. If no tool is needed, answer briefly without numbers."
    )
    for _ in range(3):
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions=instructions,
            input=messages,
            tools=TOOLS,
        )
        messages.extend(response.output)
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            return response.output_text
        for call in calls:
            arguments = json.loads(call.arguments)
            if call.name == "get_sales_summary":
                result: object = get_sales_summary(data)
            elif call.name == "get_forecast":
                result = get_forecast(data, arguments["days"])
            else:
                result = {"error": "Unknown tool"}
            messages.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)})
    return "The assistant could not complete the requested tool calls. Please try again."
