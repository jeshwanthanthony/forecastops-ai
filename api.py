"""FastAPI API and static SPA host for ForecastOps AI."""
from __future__ import annotations

import hashlib
import io
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware

from agent import answer_sales_question
from data_utils import SalesDataError, validate_sales_data
from forecasting import chronological_backtest, fit_model, recursive_forecast, seasonal_naive_forecast
from square import READ_SCOPES, SANDBOX_BASE_URL, SquareClient, SquareError, normalize_orders
from storage import TokenStore

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
STATIC = ROOT / "frontend" / "dist"
app = FastAPI(title="ForecastOps AI", docs_url="/api/docs")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32), https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true", same_site="lax")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:8001,http://localhost:5173").split(","), allow_methods=["GET", "POST"], allow_headers=["Content-Type"], allow_credentials=True)
tokens = TokenStore(str(ROOT / "forecastops.db"))


def demo_data(days: int = 730) -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(7)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days)
    weekly = np.array([.85, .8, .9, 1, 1.2, 1.35, 1.1])[dates.dayofweek]
    sales = 1800 * weekly * np.linspace(1, 1.25, days) * rng.normal(1, .07, days)
    return pd.DataFrame({"date": dates, "sales": sales.round(2), "order_count": (sales / rng.normal(19, 1.2, days)).round().astype(int)})


def dashboard(data: pd.DataFrame, report: dict | None = None) -> dict:
    model = fit_model(data)
    forecast = recursive_forecast(model, data, 7)
    baseline = seasonal_naive_forecast(data, 7)
    backtest = chronological_backtest(data)
    return {"data": [{"date": str(row.date.date()), "sales": round(float(row.sales), 2), "order_count": int(getattr(row, "order_count", 0) if pd.notna(getattr(row, "order_count", 0)) else 0)} for row in data.itertuples(index=False)], "forecast": [{"date": str(row.date.date()), "sales": round(float(row.forecast_sales), 2), "baseline": round(float(baseline.iloc[i].baseline_sales), 2)} for i, row in enumerate(forecast.itertuples(index=False))], "metrics": {"model_mae": round(backtest.model_mae, 2), "baseline_mae": round(backtest.baseline_mae, 2)}, "report": report or {}}


@app.get("/api/health")
def health(): return {"status": "ok"}

@app.get("/api/demo")
def get_demo(): return dashboard(demo_data())

@app.get("/api/sample.csv")
def sample_csv(): return FileResponse(ROOT / "data" / "sample_sales.csv", media_type="text/csv", filename="forecastops-sample.csv")

@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Upload a .csv file.")
    try:
        payload = await file.read()
        frame = pd.read_csv(io.BytesIO(payload))
        data, cleaned = validate_sales_data(frame)
        return dashboard(data, {"source": "Uploaded CSV", "duplicate_rows_aggregated": cleaned.duplicate_rows_aggregated, "missing_days_filled": cleaned.missing_days_filled})
    except (SalesDataError, UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise HTTPException(422, str(error)) from error


@app.post("/api/ask")
async def ask(body: dict):
    data = pd.DataFrame(body.get("data", [])); data["date"] = pd.to_datetime(data["date"])
    if not os.getenv("OPENAI_API_KEY"):
        return {"answer": f"Deterministic demo answer: total sales are ${data.sales.sum():,.2f}; connect an OPENAI_API_KEY for an AI tool-calling response.", "mode": "deterministic"}
    try:
        return {"answer": answer_sales_question(str(body.get("question", "")), data), "mode": "openai"}
    except Exception as error:
        raise HTTPException(502, "The configured AI analyst could not answer right now.") from error


def square_configured() -> bool:
    return not square_missing() and os.getenv("SQUARE_ENVIRONMENT", "sandbox").lower() == "sandbox"


def square_missing() -> list[str]:
    required = {"SQUARE_SANDBOX_APP_ID": square_client_id(), "SQUARE_SANDBOX_APPLICATION_SECRET": square_client_secret(), "SQUARE_REDIRECT_URI": os.getenv("SQUARE_REDIRECT_URI"), "SESSION_SECRET": os.getenv("SESSION_SECRET"), "ENCRYPTION_KEY": os.getenv("ENCRYPTION_KEY") or os.getenv("TOKEN_ENCRYPTION_KEY")}
    return [name for name, value in required.items() if not value]


def square_client_id() -> str | None:
    return os.getenv("SQUARE_CLIENT_ID") or os.getenv("SQUARE_SANDBOX_APP_ID")


def square_client_secret() -> str | None:
    return os.getenv("SQUARE_SANDBOX_APPLICATION_SECRET") or os.getenv("SQUARE_CLIENT_SECRET") or os.getenv("SQUARE_SANDBOX_APP_SECRET")


@app.get("/api/square/status")
def square_status(): return {"configured": square_configured(), "mode": "sandbox", "missing": square_missing(), "message": None if square_configured() else "Square sandbox is not configured. Check server configuration."}

@app.get("/api/config/status")
def config_status():
    """Return missing names only, never credential values."""
    missing = square_missing()
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.getenv("SQUARE_SANDBOX_ACCESS_TOKEN"):
        missing.append("SQUARE_SANDBOX_ACCESS_TOKEN")
    return {"missing": missing, "square_environment_supported": os.getenv("SQUARE_ENVIRONMENT", "sandbox").lower() == "sandbox"}

@app.get("/api/square/connect")
def square_connect(request: Request):
    if not square_configured(): raise HTTPException(503, "Square sandbox credentials are not configured.")
    state = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    request.session["square_state"] = state_hash
    tokens.issue_state(state_hash)
   
    query = urlencode({"client_id": square_client_id(), "scope": " ".join(READ_SCOPES), "state": state})







    return RedirectResponse(f"{SANDBOX_BASE_URL}/oauth2/authorize?{query}")

@app.get("/api/square/callback")
def square_callback(request: Request, state: str, code: str = "", error: str = ""):
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    saved = request.session.pop("square_state", "")
    if not saved or not secrets.compare_digest(saved, state_hash) or not tokens.consume_state(state_hash): raise HTTPException(400, "Invalid or already-used Square OAuth state.")
    if error or not code: raise HTTPException(400, "Square authorization was declined or did not return a code.")
    response = httpx.post(f"{SANDBOX_BASE_URL}/oauth2/token", json={"client_id": square_client_id(), "client_secret": square_client_secret(), "code": code, "grant_type": "authorization_code", "redirect_uri": os.environ["SQUARE_REDIRECT_URI"]}, timeout=30)
    if response.is_error: raise HTTPException(502, "Square token exchange failed.")
    token = response.json(); merchant_id = token.get("merchant_id")
    if not merchant_id or not token.get("access_token") or not token.get("refresh_token"): raise HTTPException(502, "Square returned an incomplete token response.")
    status = httpx.post(f"{SANDBOX_BASE_URL}/oauth2/token/status", headers={"Authorization": f"Bearer {token['access_token']}"}, timeout=30)
    if status.is_error or not set(READ_SCOPES).issubset(status.json().get("scopes", [])): raise HTTPException(403, "Square did not grant the required read permissions.")
    tokens.save(merchant_id, json.dumps(token))
    request.session["square_merchant_id"] = merchant_id
    return RedirectResponse("/?square=connected")

@app.get("/api/square/import")
def square_import(request: Request, days: int = 365):
    merchant_id = request.session.get("square_merchant_id")
    if not square_configured(): raise HTTPException(503, "Square sandbox configuration is incomplete.")
    stored = tokens.get(merchant_id) if merchant_id else None
    if not stored: raise HTTPException(401, "Connect a Square sandbox account first.")
    try:
        token = json.loads(stored)
        expiry = datetime.fromisoformat(token.get("expires_at", "1970-01-01T00:00:00Z").replace("Z", "+00:00"))
        if expiry <= datetime.now(timezone.utc) + timedelta(days=7):
            refreshed = httpx.post(f"{SANDBOX_BASE_URL}/oauth2/token", json={"client_id": square_client_id(), "client_secret": square_client_secret(), "grant_type": "refresh_token", "refresh_token": token["refresh_token"]}, timeout=30)
            if refreshed.is_error: raise HTTPException(401, "Square authorization expired. Reconnect the sandbox account.")
            token.update(refreshed.json())
            tokens.save(merchant_id, json.dumps(token))
        client = SquareClient(token["access_token"]); locations = client.locations()
        if not locations: raise HTTPException(422, "No Square locations were found.")
        location = locations[0]; end = datetime.now(timezone.utc); start = end - timedelta(days=max(21, min(days, 730)))
        orders, complete = client.completed_orders(location["id"], start.isoformat(), end.isoformat())
        data = normalize_orders(orders, location.get("timezone", "UTC"))
        if len(data) < 28: raise HTTPException(422, "Square returned fewer than 28 days of completed sales; forecasting needs more history.")
        return dashboard(data, {"source": "Square sandbox", "complete": complete, "location": location.get("name", location["id"])})
    except SquareError as error: raise HTTPException(502, str(error)) from error


if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

@app.get("/{path:path}")
def spa(path: str):
    target = (STATIC / path).resolve()
    if path and target.is_relative_to(STATIC.resolve()) and target.is_file():
        return FileResponse(target)
    return FileResponse(STATIC / "index.html")
