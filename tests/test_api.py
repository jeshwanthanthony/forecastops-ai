from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


def test_health_and_demo_work_without_external_credentials():
    assert client.get("/api/health").json() == {"status": "ok"}
    demo = client.get("/api/demo")
    assert demo.status_code == 200
    assert len(demo.json()["forecast"]) == 7


def test_upload_rejects_bad_csv_and_accepts_order_count():
    bad = client.post("/api/upload", files={"file": ("bad.csv", b"date,sales\nnot-date,5\n", "text/csv")})
    assert bad.status_code == 422
    rows = "date,sales,order_count\n" + "\n".join(f"2026-01-{day:02d},{100 + day},{day}" for day in range(1, 29))
    good = client.post("/api/upload", files={"file": ("sales.csv", rows.encode(), "text/csv")})
    assert good.status_code == 200
    assert len(good.json()["data"]) == 28
