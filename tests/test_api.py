from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


def test_health_and_demo_work_without_external_credentials():
    assert client.get("/api/health").json() == {"status": "ok"}
    demo = client.get("/api/demo")
    assert demo.status_code == 200
    assert len(demo.json()["forecast"]) == 7


def test_demo_scenarios_are_reproducible_and_distinct():
    from api import demo_data
    for scenario in ('normal', 'weekend', 'growth', 'seasonal', 'change'):
        assert demo_data(90, scenario).equals(demo_data(90, scenario))
    assert not demo_data(90, 'normal').equals(demo_data(90, 'weekend'))


def test_each_demo_scenario_returns_forecast():
    for scenario in ('normal', 'weekend', 'growth', 'seasonal', 'change'):
        response = client.get('/api/demo', params={'scenario': scenario})
        assert response.status_code == 200
        assert len(response.json()['forecast']) == 7


def test_csv_preview_and_mapped_import():
    rows = 'order_date;revenue\n' + '\n'.join(f'2026-01-{day:02d};1200.50' for day in range(1,29))
    content = rows.encode()
    preview = client.post('/api/csv/preview', files={'file': ('sales.csv', content, 'text/csv')})
    assert preview.status_code == 200
    assert preview.json()['candidates']['sales'] == ['revenue']
    imported = client.post('/api/csv/import', files={'file': ('sales.csv', content, 'text/csv')}, data={'date_column': 'order_date', 'sales_column': 'revenue'})
    assert imported.status_code == 200
    assert imported.json()['report']['input_rows'] == 28


def test_upload_rejects_bad_csv_and_accepts_order_count():
    bad = client.post("/api/upload", files={"file": ("bad.csv", b"date,sales\nnot-date,5\n", "text/csv")})
    assert bad.status_code == 422
    rows = "date,sales,order_count\n" + "\n".join(f"2026-01-{day:02d},{100 + day},{day}" for day in range(1, 29))
    good = client.post("/api/upload", files={"file": ("sales.csv", rows.encode(), "text/csv")})
    assert good.status_code == 200
    assert len(good.json()["data"]) == 28
