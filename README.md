# ForecastOps AI

ForecastOps takes daily sales data and estimates sales for the next seven days. Upload a CSV or use the sample data to see the forecast, sales history, and a comparison with a simple repeat-last-week baseline.

[Live site](https://forecastops.jeshwanthanthony.com) · [Python API](api.py) · [Forecasting](forecasting.py) · [React frontend](frontend/src/main.jsx) · [AWS setup](AWS.md) · [Kubernetes manifests](k8s/deployment.yaml) · [Tests](.github/workflows/tests.yml)

## Running locally

You'll need Python 3.12 and Node.js 22 or newer. From PowerShell:

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

Open http://localhost:8001. For frontend development, run `npm run dev` from `frontend` in another terminal. Vite proxies API requests to port 8001.

The sample-data demo works without external credentials. Copy `.env.example` to `.env` if you want to configure an optional integration. Keep that file out of Git.

## Input data

The CSV importer in this branch expects `date` and numeric `sales` columns, with optional `order_count`. It needs at least 28 distinct daily observations, combines duplicate dates, and reports cleaning details.

The [forecasting code](forecasting.py) uses a random forest with recent sales lags and calendar features. It predicts seven days ahead and compares its error against a seasonal-naive forecast that repeats sales from the previous week. Evaluation uses a chronological holdout rather than shuffled rows.

Both the predictions and the reported mean absolute error (MAE) are estimates, not guarantees.

## Square

The Square connector in the default branch is experimental and configured for Sandbox. It requests read-only merchant and order access. See [the API](api.py) and [.env example](.env.example) for its configuration.

The [newer development branch](https://github.com/jeshwanthanthony/forecastops-ai/tree/feature/square-oauth-codex) contains the Production OAuth, flexible CSV importer, and updated dashboard used by the live deployment. The code on `master` may therefore differ from the live website until that branch is merged.

## Docker and deployment

Build and run a local container:

```powershell
docker build -t forecastops-ai:local .
docker run --rm -p 8000:8000 forecastops-ai:local
```

The public website runs on AWS EC2, with Nginx handling HTTPS in front of a Docker container. Kubernetes is a separate local [kind](k8s/README.md) exercise; the public site does not run on EKS.

An image was pushed to private Amazon ECR, and private S3 access was checked using an EC2 IAM role. S3 is not used to store application forecasts. The commands and evidence are in [AWS.md](AWS.md) and [deployment notes](docs/DEPLOYMENT_EVIDENCE.md).

## Tests

```powershell
python -m pytest
cd frontend
npm run build
```

See [GitHub Actions](https://github.com/jeshwanthanthony/forecastops-ai/actions) for CI results and the [Kubernetes smoke-test workflow](.github/workflows/kubernetes-smoke.yml) for the kind deployment check.
