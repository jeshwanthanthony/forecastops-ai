# ForecastOps AI

ForecastOps AI explores daily sales history, a seven-day forecast, and model accuracy. Try the synthetic demo or upload a CSV with `date`, `sales`, and optional `order_count`. At least 28 distinct dates are required.

React and Vite provide the interface. FastAPI serves the built frontend and calls the existing Python forecasting and analyst modules. The random forest is compared with a seasonal-naive baseline using a chronological holdout.

## Local setup

Install Python 3.12 and Node.js 22 or later. In PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
cd frontend
npm install
npm run build
cd ..
python -m pytest
python -m uvicorn api:app --reload --port 8001
```

Open `http://localhost:8001`. The health endpoint is `/api/health`; API documentation is at `/api/docs`.

For frontend development, run `npm run dev` in `frontend` in a second terminal while the backend is running. Vite prints its local URL and proxies `/api` requests to port 8001.

## Configuration

The backend loads `.env` automatically. Leave `OPENAI_API_KEY` blank to use the deterministic demo response; set it to enable the existing OpenAI analyst. Never put secrets in `VITE_` variables: Vite embeds them in browser code. No frontend environment variables are required for local use.

Square is sandbox-only and experimental. Set `SQUARE_SANDBOX_APP_ID`, `SQUARE_SANDBOX_APPLICATION_SECRET`, and the exact registered `SQUARE_REDIRECT_URI`; leave `SQUARE_ENVIRONMENT=sandbox`. The optional `SQUARE_SANDBOX_ACCESS_TOKEN` is a full-access personal sandbox test token, not an OAuth seller token; it is not used for seller imports. Set a long random `SESSION_SECRET` and a stable `ENCRYPTION_KEY` (URL-safe base64 encoding of 32 random bytes) to retain encrypted tokens across restarts. Generate a key with:

```powershell
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

`SQUARE_CLIENT_ID`, `SQUARE_CLIENT_SECRET`, `SQUARE_SANDBOX_APP_SECRET`, and `TOKEN_ENCRYPTION_KEY` remain supported as alternatives. Without persistent keys, sessions and stored sandbox tokens will not survive a restart. Set `COOKIE_SECURE=true` behind HTTPS. The OAuth flow and token refresh have not been verified against a live sandbox; refund handling remains incomplete. Do not use real seller data. `AWS_REGION` and `S3_BUCKET_NAME` are placeholders; S3 is not implemented.

## Docker

```powershell
docker build -t forecastops-ai:local .
docker run --rm -p 8000:8000 --env-file .env forecastops-ai:local
```

The multistage build compiles the frontend and serves it from the FastAPI container. Omit `--env-file .env` if no optional integrations are configured.

## Local Kubernetes

```powershell
kind load docker-image forecastops-ai:local --name forecastops
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl rollout status deployment/forecastops-ai
kubectl get pods -l app=forecastops-ai
kubectl port-forward service/forecastops-ai 8000:8000
```

The deployment uses health probes. Demo scaling can be checked with `kubectl scale deployment/forecastops-ai --replicas=3`, then returned to one with `kubectl scale deployment/forecastops-ai --replicas=1`. Square token storage is local to each process and is not suitable for multiple replicas. See [AWS.md](AWS.md) for the optional ECR, EKS, and S3 plan; no AWS resources have been created.
