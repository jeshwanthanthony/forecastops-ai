"""Small server-side, sandbox-only Square OAuth and order import client."""
from __future__ import annotations

import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

SANDBOX_BASE_URL = "https://connect.squareupsandbox.com"
PRODUCTION_BASE_URL = "https://connect.squareup.com"
SQUARE_VERSION = "2026-09-16"
READ_SCOPES = ("MERCHANT_PROFILE_READ", "ORDERS_READ")


class SquareError(RuntimeError):
    pass


class SquareClient:
    """Bounded request and cursor handling. Production is deliberately unsupported."""

    def __init__(self, access_token: str, *, transport: httpx.BaseTransport | None = None, base_url: str = SANDBOX_BASE_URL):
        self.access_token, self.transport, self.base_url = access_token, transport, base_url

    def _request(self, method: str, path: str, **kwargs) -> dict:
        headers = {"Authorization": f"Bearer {self.access_token}", "Square-Version": SQUARE_VERSION}
        for attempt in range(4):
            with httpx.Client(base_url=self.base_url, timeout=30, transport=self.transport) as client:
                response = client.request(method, path, headers=headers, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 3:
                    break
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else min(8, 2**attempt + random.random())
                time.sleep(delay)
                continue
            if response.status_code in (401, 403):
                raise SquareError("Square authorization expired or is missing required permissions. Reconnect the sandbox account.")
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise SquareError(f"Square request failed ({response.status_code}).") from error
            return response.json()
        raise SquareError("Square rate limit or service error persisted after bounded retries.")

    def locations(self) -> list[dict]:
        return self._request("GET", "/v2/locations").get("locations", [])

    def completed_orders(self, location_id: str, start_at: str, end_at: str, max_pages: int = 200) -> tuple[list[dict], bool]:
        orders, cursor = [], None
        for _ in range(max_pages):
            body = {"location_ids": [location_id], "query": {"filter": {"state_filter": {"states": ["COMPLETED"]}, "date_time_filter": {"closed_at": {"start_at": start_at, "end_at": end_at}}}, "sort": {"sort_field": "CLOSED_AT", "sort_order": "ASC"}}, "limit": 500}
            if cursor:
                body["cursor"] = cursor
            response = self._request("POST", "/v2/orders/search", json=body)
            orders.extend(response.get("orders", []))
            cursor = response.get("cursor")
            if not cursor:
                return orders, True
        return orders, False


def normalize_orders(orders: list[dict], timezone: str) -> pd.DataFrame:
    """Convert completed Square orders to the project's daily forecast schema.

    Refunds embedded in an order are deducted on the order's local close date.
    Missing days are zero-filled so the model sees a regular daily series.
    """
    rows = []
    zone = ZoneInfo(timezone)
    for order in orders:
        closed_at = order.get("closed_at")
        if not closed_at:
            continue
        local = datetime.fromisoformat(closed_at.replace("Z", "+00:00")).astimezone(zone)
        money = lambda value: int((value or {}).get("amount", 0))
        refunds = sum(money(item.get("amount_money")) for item in order.get("refunds", []))
        net_cents = money(order.get("total_money")) - money(order.get("total_tax_money")) - money(order.get("total_tip_money")) - refunds
        rows.append({"date": pd.Timestamp(local.date()), "sales": net_cents / 100, "order_id": order.get("id")})
    if not rows:
        return pd.DataFrame(columns=["date", "sales", "order_count"])
    daily = pd.DataFrame(rows).groupby("date", as_index=False).agg(sales=("sales", "sum"), order_count=("order_id", "nunique"))
    dates = pd.date_range(daily.date.min(), daily.date.max(), freq="D")
    return daily.set_index("date").reindex(dates, fill_value=0).rename_axis("date").reset_index()
