import httpx
import base64
import os

from square import SquareClient, normalize_orders
from storage import TokenStore


def test_search_orders_follows_cursor_with_mocked_square_responses():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"orders": [{"id": str(len(calls))}], **({"cursor": "next"} if len(calls) == 1 else {})})
    client = SquareClient("test", transport=httpx.MockTransport(handler))
    orders, complete = client.completed_orders("L1", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z")
    assert complete is True
    assert [order["id"] for order in orders] == ["1", "2"]
    assert b'"cursor":"next"' in calls[1].content


def test_normalize_orders_uses_location_timezone_and_refunds():
    orders = [{"id": "one", "closed_at": "2026-01-02T04:30:00Z", "total_money": {"amount": 1200}, "total_tax_money": {"amount": 100}, "total_tip_money": {"amount": 200}, "refunds": [{"amount_money": {"amount": 300}}]}]
    daily = normalize_orders(orders, "America/New_York")
    assert str(daily.date.iloc[0].date()) == "2026-01-01"
    assert daily.sales.iloc[0] == 6


def test_oauth_state_can_be_consumed_only_once(tmp_path):
    key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    store = TokenStore(str(tmp_path / "test.db"), key)
    store.issue_state("digest")
    assert store.consume_state("digest") is True
    assert store.consume_state("digest") is False
