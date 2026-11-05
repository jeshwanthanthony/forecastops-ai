# ForecastOps AI

ForecastOps turns daily sales data into a seven-day forecast and compares it with a seasonal-naive baseline. Data can come from a CSV, a temporary Square connection, or a synthetic restaurant demo.

[Live application](https://forecastops.jeshwanthanthony.com) · [Backend](api.py) · [Forecasting](forecasting.py) · [Square](square.py) · [AWS](AWS.md) · [Deployment evidence](docs/DEPLOYMENT_EVIDENCE.md) · [Kubernetes manifest](k8s/deployment.yaml) · [Kubernetes smoke workflow](.github/workflows/kubernetes-smoke.yml) · [Python tests](.github/workflows/tests.yml)

The [React workspace](frontend/src/ResultsDashboard.jsx) shows sales history, a seven-day outlook, weekday averages, and model error. Drag a CSV into the upload card to preview and map its columns, or use the synthetic scenarios to explore different demand patterns. Chart points expose their dates and values on hover or keyboard focus. The pipeline panel describes the data and evaluation actually used.

[![Python tests](https://github.com/jeshwanthanthony/forecastops-ai/actions/workflows/tests.yml/badge.svg?branch=feature%2Fsquare-oauth-codex)](https://github.com/jeshwanthanthony/forecastops-ai/actions/workflows/tests.yml) [![Kubernetes smoke](https://github.com/jeshwanthanthony/forecastops-ai/actions/workflows/kubernetes-smoke.yml/badge.svg?branch=feature%2Fsquare-oauth-codex)](https://github.com/jeshwanthanthony/forecastops-ai/actions/workflows/kubernetes-smoke.yml)

## How it works

React presents the data; FastAPI validates it and serves the built frontend. Pandas aggregates daily sales, and a lightweight model forecasts the next week. Square imports run in a bounded background worker using the visitor's OAuth token. SQLite stores encrypted, temporary connection credentials.

The forecast uses a seasonal-naive model for shorter histories and Ridge regression for longer histories. Evaluation holds out the latest observations in chronological order. MAE is the average absolute difference between the forecast and actual sales; it is not a guarantee of future accuracy.

## Run locally

Install Python 3.12 and Node.js 22 or later, then run in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python -m pytest
python -m uvicorn api:app --reload --port 8001
```

Open http://localhost:8001. For frontend development, run `npm run dev` in `frontend` while the backend is running. Copy `.env.example` to `.env` only if you need an optional integration; keep `.env` private.

## Data and integrations

CSV uploads preview their columns and suggest common date and sales names; choose a mapping and explicitly select month/day or day/month for ambiguous slash dates. UTF-8, UTF-8 BOM, Windows-1252, comma, semicolon, and tab files are supported. Duplicate transaction dates are summed, missing dates are zero-filled, and malformed rows are rejected. At least 28 distinct dates are required; limits are 5 MB and 100,000 rows. Timestamps are grouped by UTC date. The selected sales column is used as supplied: gross and net sales are not converted into each other.

Square requests read-only merchant and order permissions; visitor connections are temporary browser sessions, not accounts. The optional OpenAI analyst uses function calls against the loaded data; without a key the demo uses a labeled deterministic response.

Imported Square sales are estimates and are not reconciled accounting reports. Refunds, taxes, tips, multiple currencies, and incomplete imports can affect the results. A forecast cannot predict unexpected events.

## Infrastructure and tests

The public deployment runs Docker on EC2 behind Nginx and HTTPS. An image was pushed to private ECR and private S3 access was tested; the application does not currently export forecasts to S3. Kubernetes is tested separately with kind, not used for the EC2 production deployment. See [AWS notes](AWS.md), [deployment evidence](docs/DEPLOYMENT_EVIDENCE.md), and [kind instructions](k8s/README.md).

```powershell
python -m pytest
cd frontend
npm run build
```

See [GitHub Actions](https://github.com/jeshwanthanthony/forecastops-ai/actions) for actual workflow results. Production OAuth, proxy configuration, temporary-session handling, and rate limits require careful verification before making changes to the live service.
