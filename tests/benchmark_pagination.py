"""Measure mocked page processing; excludes real network and container memory."""
import time
import tracemalloc

import httpx

from square import SquareClient, normalize_orders


def main():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        page = [{"id": str(i), "closed_at": "2026-01-01T12:00:00Z", "total_money": {"amount": 2000}} for i in range(500)]
        return httpx.Response(200, json={"orders": page, **({"cursor": str(calls)} if calls < 50 else {})})
    client = SquareClient("mock", transport=httpx.MockTransport(handler))
    tracemalloc.start()
    start = time.perf_counter()
    count = 0
    for page, _ in client.completed_order_pages("location", "start", "end", 50):
        count += len(page)
        normalize_orders(page, "UTC")
    print(f"orders={count} pages={calls} seconds={time.perf_counter()-start:.2f} traced_peak_mib={tracemalloc.get_traced_memory()[1]/1048576:.2f}")


if __name__ == "__main__":
    main()
