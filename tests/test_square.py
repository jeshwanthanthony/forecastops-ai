import httpx
import base64
import os
import pytest

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


def test_pagination_streams_25000_orders_without_accumulating():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"orders": [{"id": str(i)} for i in range(500)], **({"cursor": str(calls)} if calls < 50 else {})})
    client = SquareClient("test", transport=httpx.MockTransport(handler))
    count = 0
    for page, complete in client.completed_order_pages("loc", "start", "end", max_pages=50):
        assert len(page) == 500
        count += len(page)
    assert count == 25000 and complete and calls == 50


def test_cancellation_stops_before_next_page():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"orders": [], "cursor": "more"})
    def check():
        if calls:
            raise RuntimeError("cancelled")
    client = SquareClient("test", transport=httpx.MockTransport(handler), check=check)
    with pytest.raises(RuntimeError, match="cancelled"):
        list(client.completed_order_pages("loc", "start", "end"))
    assert calls == 1


@pytest.mark.parametrize("status", [429, 503])
def test_rate_limit_and_server_errors_are_retried(monkeypatch, status):
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"locations": []})
    monkeypatch.setattr("square.time.sleep", lambda _: None)
    client = SquareClient("test", transport=httpx.MockTransport(handler))
    assert client.locations() == []
    assert calls == 2
