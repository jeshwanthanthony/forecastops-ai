"""Regression tests for read-only Square Production OAuth and visitor isolation."""
import base64
import os
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi.testclient import TestClient

from api import app, square_missing, square_configured
from square import PRODUCTION_BASE_URL, SquareClient
from storage import TokenStore


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
        response = client.get("/api/square/import")
        assert response.status_code == 401
