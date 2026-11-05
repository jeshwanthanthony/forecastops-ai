"""Regression tests for read-only Square Production OAuth and visitor isolation."""
import base64
import os
import json
import time
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi.testclient import TestClient

from api import app, square_missing, square_configured
from square import PRODUCTION_BASE_URL, SquareClient
from storage import TokenStore
import api
import pytest


def production_config(monkeypatch):
    monkeypatch.setenv("SQUARE_ENVIRONMENT", "production")
    monkeypatch.setenv("SQUARE_PRODUCTION_APP_ID", "sq0idp-test-client")
    monkeypatch.setenv("SQUARE_PRODUCTION_APPLICATION_SECRET", "sq0csp-test-secret")
    monkeypatch.setenv("SQUARE_REDIRECT_URI", "https://forecastops.jeshwanthanthony.com/api/square/callback")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
    monkeypatch.setenv("COOKIE_SECURE", "true")


def test_production_oauth_redirect_uses_production_domain_scopes_and_signin(monkeypatch):
    production_config(monkeypatch)
    assert square_configured()
    with TestClient(app) as client:
        response = client.get("/api/square/connect", follow_redirects=False)
        assert response.status_code in (302, 303, 307)
        url = urlsplit(response.headers["location"])
        params = parse_qs(url.query)
        assert url.netloc == "connect.squareup.com"
        assert url.path == "/oauth2/authorize"
        assert params["client_id"] == ["sq0idp-test-client"]
        assert params["session"] == ["false"]
        assert set(params["scope"][0].split()) == {"ORDERS_READ", "MERCHANT_PROFILE_READ"}
        assert params["state"][0]
        assert "secret" not in response.headers["location"]


def test_production_requires_https_and_secure_cookies(monkeypatch):
    production_config(monkeypatch)
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("SQUARE_REDIRECT_URI", "http://localhost:8001/api/square/callback")
    missing = square_missing()
    assert "COOKIE_SECURE=true" in missing
    assert "SQUARE_REDIRECT_URI (public HTTPS URL required)" in missing


def test_production_does_not_fall_back_to_generic_credentials(monkeypatch):
    production_config(monkeypatch)
    monkeypatch.delenv("SQUARE_PRODUCTION_APP_ID")
    monkeypatch.delenv("SQUARE_PRODUCTION_APPLICATION_SECRET")
    monkeypatch.setenv("SQUARE_CLIENT_ID", "sandbox-client")
    monkeypatch.setenv("SQUARE_CLIENT_SECRET", "sandbox-secret")
    assert not square_configured()


def test_visitor_connections_have_independent_encrypted_tokens(tmp_path):
    key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    store = TokenStore(str(tmp_path / "tokens.db"), key)
    store.save_connection("visitor-A", "merchant A")
    store.save_connection("visitor-B", "merchant B")
    assert store.get_connection("visitor-A") == "merchant A"
    assert store.get_connection("visitor-B") == "merchant B"
    store.delete_connection("visitor-A")
    assert store.get_connection("visitor-A") is None
    assert store.get_connection("visitor-B") == "merchant B"


def test_square_client_calls_production_not_sandbox():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"locations": []})
    client = SquareClient("seller-token", base_url=PRODUCTION_BASE_URL,
                          transport=httpx.MockTransport(handler))
    assert client.locations() == []
    assert requests[0].url.host == "connect.squareup.com"
    assert requests[0].headers["Authorization"] == "Bearer seller-token"


def test_public_visitor_without_authorization_cannot_import(monkeypatch):
    production_config(monkeypatch)
    with TestClient(app) as client:
        response = client.post("/api/square/import/jobs")
        assert response.status_code == 401


@pytest.fixture
def isolated_store(monkeypatch, tmp_path):
    production_config(monkeypatch)
    store = TokenStore(str(tmp_path / "visitors.db"), base64.urlsafe_b64encode(os.urandom(32)).decode())
    monkeypatch.setattr(api, "tokens", store)
    return store


def test_callback_state_is_bound_to_browser_and_single_use(monkeypatch, isolated_store):
    calls = []
    def square_post(url, **kwargs):
        calls.append(url)
        if url.endswith("/token/status"):
            return httpx.Response(200, json={"scopes": ["ORDERS_READ", "MERCHANT_PROFILE_READ"]})
        return httpx.Response(200, json={"merchant_id": "seller", "access_token": "access", "refresh_token": "refresh"})
    monkeypatch.setattr(api.httpx, "post", square_post)
    with TestClient(app) as visitor_a, TestClient(app) as visitor_b:
        redirect = visitor_a.get("/api/square/connect", follow_redirects=False)
        state = parse_qs(urlsplit(redirect.headers["location"]).query)["state"][0]
        assert visitor_b.get("/api/square/callback", params={"code": "x", "state": state}).status_code == 400
        assert calls == []
        assert visitor_a.get("/api/square/callback", params={"code": "x", "state": state}, follow_redirects=False).status_code == 303
        assert visitor_a.get("/api/square/callback", params={"code": "x", "state": state}).status_code == 400
        assert visitor_b.get("/api/square/session").json()["connected"] is False
        assert visitor_b.post("/api/square/import/jobs").status_code == 401


def test_callback_handles_square_outage(monkeypatch, isolated_store):
    def outage(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(api.httpx, "post", outage)
    with TestClient(app) as client:
        state = parse_qs(urlsplit(client.get("/api/square/connect", follow_redirects=False).headers["location"]).query)["state"][0]
        assert client.get("/api/square/callback", params={"code": "x", "state": state}).status_code == 502


def test_import_refreshes_and_handles_empty_locations(monkeypatch, isolated_store):
    token = {"access_token": "old", "refresh_token": "refresh", "expires_at": "2020-01-01T00:00:00Z"}
    isolated_store.save_connection("visitor", json.dumps(token))
    monkeypatch.setattr(api.httpx, "post", lambda *args, **kwargs: httpx.Response(200, json={"access_token": "new", "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}))
    monkeypatch.setattr(api.SquareClient, "locations", lambda self: [{"id": "a"}, {"id": "b"}])
    monkeypatch.setattr(api.SquareClient, "completed_order_pages", lambda *args, **kwargs: iter([([], True)]))
    with TestClient(app) as client:
        from itsdangerous import TimestampSigner
        import base64 as b64
        payload = b64.b64encode(json.dumps({"square_connection_id": "visitor"}).encode())
        middleware = next(item for item in app.user_middleware if item.cls.__name__ == "SessionMiddleware")
        signer = TimestampSigner(middleware.kwargs["secret_key"])
        client.cookies.set("session", signer.sign(payload).decode())
        response = wait_for_job(client)
        assert response["status"] == "failed"
        assert "no completed orders" in response["error"]
        assert json.loads(isolated_store.get_connection("visitor"))["access_token"] == "new"


def test_disconnect_rejects_cross_origin(monkeypatch, isolated_store):
    with TestClient(app) as client:
        assert client.post("/api/square/disconnect", headers={"Origin": "https://attacker.example"}).status_code == 403


def test_independent_visitors_and_disconnect_revocation(monkeypatch, isolated_store):
    observed = []
    def square_post(url, **kwargs):
        if url.endswith("/token/status"):
            return httpx.Response(200, json={"scopes": list(api.READ_SCOPES)})
        if url.endswith("/revoke"):
            observed.append(kwargs["json"]["access_token"])
            return httpx.Response(200, json={"success": True})
        code = kwargs["json"]["code"]
        return httpx.Response(200, json={"merchant_id": code, "access_token": code, "refresh_token": "r", "expires_at": "2099-01-01T00:00:00Z"})
    monkeypatch.setattr(api.httpx, "post", square_post)
    def login(client, seller):
        url = client.get("/api/square/connect", follow_redirects=False).headers["location"]
        state = parse_qs(urlsplit(url).query)["state"][0]
        assert client.get("/api/square/callback", params={"state": state, "code": seller}, follow_redirects=False).status_code == 303
    with TestClient(app) as first, TestClient(app) as second:
        login(first, "seller-a")
        login(second, "seller-b")
        assert first.get("/api/square/session").json()["connected"]
        assert second.get("/api/square/session").json()["connected"]
        result = first.post("/api/square/disconnect", headers={"Origin": "https://forecastops.jeshwanthanthony.com"})
        assert result.json()["square_revoked"] is True
        assert observed == ["seller-a"]
        assert not first.get("/api/square/session").json()["connected"]
        assert second.get("/api/square/session").json()["connected"]


def test_multiple_locations_are_combined(monkeypatch, isolated_store):
    token = {"access_token": "access", "refresh_token": "refresh", "expires_at": "2099-01-01T00:00:00Z"}
    isolated_store.save_connection("visitor", json.dumps(token))
    monkeypatch.setattr(api.SquareClient, "locations", lambda self: [{"id": "a", "currency": "USD"}, {"id": "b", "currency": "USD"}])
    def orders(self, location, *args, **kwargs):
        rows = [{"id": f"{location}-{day}", "closed_at": f"2026-01-{day:02d}T12:00:00Z", "total_money": {"amount": 1000 if location == "a" else 2000}} for day in range(1, 29)]
        return rows, True
    monkeypatch.setattr(api.SquareClient, "completed_order_pages", lambda *args, **kwargs: iter([orders(*args, **kwargs)]))
    with TestClient(app) as client:
        from itsdangerous import TimestampSigner
        middleware = next(item for item in app.user_middleware if item.cls.__name__ == "SessionMiddleware")
        payload = base64.b64encode(json.dumps({"square_connection_id": "visitor"}).encode())
        client.cookies.set("session", TimestampSigner(middleware.kwargs["secret_key"]).sign(payload).decode())
        response = wait_for_job(client)
        assert response["status"] == "completed"
        assert response["result"]["report"]["locations"] == 2
        assert response["result"]["data"][0]["sales"] == 30


def test_expensive_endpoints_are_rate_limited(isolated_store):
    api._rate_events.clear()
    with TestClient(app) as client:
        for _ in range(15):
            assert client.post("/api/square/import/jobs").status_code == 401
        assert client.post("/api/square/import/jobs").status_code == 429
    api._rate_events.clear()


def wait_for_job(client):
    response = client.post("/api/square/import/jobs")
    assert response.status_code == 202
    path = "/api/square/import/jobs/" + response.json()["job_id"]
    for _ in range(200):
        result = client.get(path).json()
        if result["status"] in ("completed", "failed", "cancelled"):
            return result
        time.sleep(.05)
    pytest.fail("Import did not finish")


def test_jobs_are_private_and_duplicate_requests_reuse_active_job(monkeypatch, isolated_store):
    entered, release = threading.Event(), threading.Event()
    def slow_import(request, days):
        entered.set()
        release.wait(5)
        return {"ok": True}
    monkeypatch.setattr(api, "square_import", slow_import)
    isolated_store.save_connection("owner-a", "{}")
    isolated_store.save_connection("owner-b", "{}")
    from itsdangerous import TimestampSigner
    middleware = next(item for item in app.user_middleware if item.cls.__name__ == "SessionMiddleware")
    signer = TimestampSigner(middleware.kwargs["secret_key"])
    with TestClient(app) as first, TestClient(app) as second:
        for client, owner in [(first, "owner-a"), (second, "owner-b")]:
            payload = base64.b64encode(json.dumps({"square_connection_id": owner}).encode())
            client.cookies.set("session", signer.sign(payload).decode())
        api._rate_events.clear()
        job = first.post("/api/square/import/jobs").json()["job_id"]
        assert entered.wait(2)
        assert first.post("/api/square/import/jobs").json()["job_id"] == job
        assert second.get(f"/api/square/import/jobs/{job}").status_code == 404
        assert second.post("/api/square/import/jobs").status_code == 429
        assert second.get("/api/health").status_code == 200
        release.set()
        for _ in range(100):
            if first.get(f"/api/square/import/jobs/{job}").json()["status"] == "completed":
                break
            time.sleep(.02)
        else:
            pytest.fail("Background job did not complete")
