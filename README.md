Kubernetes: https://github.com/jeshwanthanthony/forecastops-ai/tree/master/k8s  
AWS: https://github.com/jeshwanthanthony/forecastops-ai/blob/master/AWS.md

# ForecastOps AI

Live: https://forecastops.jeshwanthanthony.com

I built ForecastOps to see what next week's sales might look like using past sales. You can upload a CSV or try it with sample data. It shows a seven-day forecast, daily sales patterns, and how the model did compared with a simple baseline.

The backend is Python and FastAPI, with Pandas for the sales data. React handles the dashboard. The code is in [api.py](api.py), [forecasting.py](forecasting.py), and [frontend](frontend/).

### Run it locally

You'll need Python 3.12 and Node.js 22+. From PowerShell:

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

Open http://localhost:8001.

The CSV loader on `master` expects `date` and `sales` columns and at least 28 days of data. Run tests with `python -m pytest`.

### Where it's running

The live site runs in Docker on an AWS EC2 instance behind Nginx. The Kubernetes setup is a separate local kind demo, not what hosts the website. There's also a [GitHub Actions Kubernetes test](.github/workflows/kubernetes-smoke.yml).

I've pushed an image to Amazon ECR and tested private S3 access. The app doesn't save forecasts to S3.

The [newer app code](https://github.com/jeshwanthanthony/forecastops-ai/tree/feature/square-oauth-codex) includes Square Production OAuth, more flexible CSV uploads, and the latest dashboard. That's the version used on the live site; `master` hasn't been merged with it yet.
