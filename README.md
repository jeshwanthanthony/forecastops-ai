Kubernetes: [![Kubernetes kind test](https://github.com/jeshwanthanthony/forecastops-ai/actions/workflows/kubernetes-smoke.yml/badge.svg?branch=master)](https://github.com/jeshwanthanthony/forecastops-ai/actions/runs/41956496746) | AWS: [![AWS EC2 deployed](https://img.shields.io/badge/AWS%20EC2-deployed-brightgreen)](AWS.md)

# Forecast

Live: https://forecastops.jeshwanthanthony.com

Forecast is a Dockerized full-stack sales-forecasting project using Python, FastAPI, Pandas, scikit-learn, React, and Vite for CSV schema detection, Square Production OAuth imports, daily time-series aggregation, lag and calendar feature engineering, Ridge and seasonal-naive forecasts, chronological backtesting, and interactive sales dashboards, with the website hosted on AWS EC2 behind Nginx and HTTPS and separate ECR, S3, Kubernetes kind, and GitHub Actions exercises.

The main parts are [api.py](api.py), [forecasting.py](forecasting.py), [Square integration](square.py), [CSV handling](data_utils.py), and the [React dashboard](frontend/src/ResultsDashboard.jsx).

## Run it locally

Use Python 3.12 and Node.js 22 or newer:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python -m uvicorn api:app --reload --port 8001
```

Open http://localhost:8001. For frontend changes, run `npm run dev` from `frontend` in another terminal. The API needs to be running for the demo and CSV import to work.

## What you can try

- **CSV:** Drop a file onto the upload area or browse for one. The importer previews columns, suggests date and sales fields, and lets you correct the mapping. It handles common encodings and comma, semicolon, or tab delimiters. It needs at least 28 days of usable data and limits uploads to 5 MB and 100,000 rows.
- **Square:** Authorize read-only merchant and order access. The connection uses a temporary browser session, not a permanent account. The resulting sales totals are estimates, not Square accounting reports.
- **Demo:** Try the fictional restaurant data and switch between the synthetic sales patterns. No credentials are needed.

The model uses a seasonal-naive method for short histories and Ridge regression for longer ones. The latest dates are held out to compare its error against the baseline. MAE is the average size of those errors, not a promise about future sales.

## Docker, AWS, and Kubernetes

The public site runs in Docker on EC2. It does **not** run on Kubernetes. I used [kind](k8s/README.md) locally and in a [GitHub Actions smoke test](https://github.com/jeshwanthanthony/forecastops-ai/actions/runs/41956496746). That successful test was for an earlier commit, not necessarily this branch's latest code.

I pushed a Docker image to private ECR and tested S3 access with an IAM role, but deployment is still manual and the app doesn't save reports to S3. See [AWS.md](AWS.md) and [the deployment notes](docs/DEPLOYMENT_EVIDENCE.md).

## Tests

```powershell
python -m pytest
cd frontend
npm run build
```

[GitHub Actions](https://github.com/jeshwanthanthony/forecastops-ai/actions) has the workflow results. The [EC2 checklist](EC2-REVIEW.md) covers the Square and session checks still worth doing before wider use.
