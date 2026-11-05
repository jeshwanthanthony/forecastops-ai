# ForecastOps AI

**AI sales forecasting | Python · FastAPI · React · Docker · Kubernetes (kind) · AWS EC2 · ECR · S3 · GitHub Actions**

**[Live HTTPS demo](https://forecastops.jeshwanthanthony.com)** · **[Deployment evidence](docs/DEPLOYMENT_EVIDENCE.md)** · **[Kubernetes manifests and instructions](k8s/README.md)**

A containerized sales-forecasting portfolio project with a public AWS EC2 deployment and a separate, reproducible local Kubernetes kind deployment. The public EC2 server runs Docker, **not EKS or K3s**. Square Production OAuth is under development separately; the current main-branch Square integration is for Sandbox testing.


ForecastOps AI explores daily sales history, a seven-day forecast, and model accuracy. Try the synthetic demo or upload a CSV with `date`, `sales`, and optional `order_count`. At least 28 distinct dates are required.

React and Vite provide the interface. FastAPI serves the built frontend and calls the Python forecasting and analyst modules. A seasonal-naive forecast is used for short histories; longer histories use regularized Ridge regression. Both are compared with a seasonal-naive baseline using a chronological holdout.

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

Square Sandbox is available for local development. The public Square connector can use **Production OAuth**: each visitor signs in to their own Square account, grants `MERCHANT_PROFILE_READ` and `ORDERS_READ`, and ForecastOps uses that visitor's access token to read completed orders. **The Production personal access token is not used or needed**; do not copy it to EC2.

For a Production deployment, register **exactly** `https://forecastops.jeshwanthanthony.com/api/square/callback` in your Square Developer Console under **Production → OAuth**. Configure these server-side environment variables (never in Git or the React frontend):

```dotenv
SQUARE_ENVIRONMENT=production
SQUARE_PRODUCTION_APP_ID=
SQUARE_PRODUCTION_APPLICATION_SECRET=
SQUARE_REDIRECT_URI=https://forecastops.jeshwanthanthony.com/api/square/callback
SESSION_SECRET=
ENCRYPTION_KEY=
COOKIE_SECURE=true
PUBLIC_ORIGIN=https://forecastops.jeshwanthanthony.com
```

Use a long random `SESSION_SECRET` and a stable URL-safe base64 AES-256 `ENCRYPTION_KEY`. Generate the encryption key with `python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`. Give the environment file restrictive permissions (0600). Restart the Docker application with the updated environment file. The public reverse proxy must route `/api/square/` to FastAPI instead of returning 404; keep `/api/config/`, `/api/docs`, and `/openapi.json` private.

OAuth uses single-use state and signed secure, HTTP-only, same-site cookies. Tokens are AES-GCM-encrypted and isolated using a random connection ID for each visitor's **temporary six-hour session**, never keyed solely by the merchant ID. The disconnect action requests Square revocation and removes local credentials; if revocation fails, visitors must revoke access in their Square Dashboard. This **is not a permanent logged-in SaaS account system**. Reconnecting is required when the session expires or the server's local token storage is deleted. Don't use it for storing long-term customer data without additional identity, audit, retention, and access-control work.

An import reads up to 365 days of completed orders from active locations, aggregates to daily sales, and produces a forecast if at least 28 days of observations exist. Results are estimates; refunds, third-party adjustments, and reconciliation may differ from Square's accounting reports. Accounts without completed orders receive a clear message; the sample-data demo still works.

Before allowing outside merchants, verify Production OAuth end to end with multiple real authorized test sellers, including cross-browser isolation, cancellation, disconnect/revocation, token refresh, and error handling. **A passing mock test is not evidence of a live Production authorization.** The in-memory request limiter is a single-process guard; configure trusted proxy addresses and independent edge limits. Uploads are limited to 5 MB. Public OpenAI calls are disabled by default in production; keep them disabled until per-user quota controls exist. Session expiry removes local credentials but does not revoke the seller's Square authorization; sellers must disconnect in Square to revoke it. See [EC2-REVIEW.md](EC2-REVIEW.md) before deployment.

In Sandbox mode, use `SQUARE_SANDBOX_APP_ID`, `SQUARE_SANDBOX_APPLICATION_SECRET`, `SQUARE_REDIRECT_URI=http://localhost:8001/api/square/callback`, and `SQUARE_ENVIRONMENT=sandbox`. The optional personal Sandbox token is not used for seller OAuth. `SQUARE_CLIENT_ID` and `SQUARE_CLIENT_SECRET` are supported as legacy Sandbox aliases only; Production requires the explicitly named Production credentials. `TOKEN_ENCRYPTION_KEY` remains an encryption-key alias.

`AWS_REGION` and `S3_BUCKET_NAME` are placeholders; S3 is not implemented.

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

The deployment uses health probes. Demo scaling can be checked with `kubectl scale deployment/forecastops-ai --replicas=3`, then returned to one with `kubectl scale deployment/forecastops-ai --replicas=1`. Square token storage is local to each process and is not suitable for multiple replicas. See [Kubernetes reproduction steps](k8s/README.md) and [AWS.md](AWS.md). The Docker image was pushed to private AWS ECR as `v1`, and a private S3 test upload succeeded; S3 report storage is **not yet integrated into the application**.


## Real infrastructure evidence

| Capability | Verified project work |
| --- | --- |
| **AWS EC2, Docker, Nginx, HTTPS** | Public app is deployed to the EC2 Docker server behind a custom-domain TLS reverse proxy. |
| **AWS IAM** | EC2 uses an assumed IAM role instead of embedded AWS access keys. |
| **Amazon ECR** | Published `forecastops-ai:v1` container to private ECR in `us-east-2`. |
| **Amazon S3** | Uploaded a private test artifact under the IAM-restricted `reports/` prefix. The application does not yet write forecast reports to S3. |
| **Kubernetes** | `k8s/deployment.yaml` and `k8s/service.yaml` support a local kind deployment; a GitHub Actions smoke test builds the image and checks its health inside kind. |

See [deployment evidence, exact resource names, and verification commands](docs/DEPLOYMENT_EVIDENCE.md). Check the GitHub [Actions](../../actions) page for **actual** CI results; a workflow file alone is not proof of a passed run.

### Resume-ready project line

**ForecastOps AI | Python, FastAPI, React, Docker, Kubernetes (kind), AWS EC2, ECR, S3, GitHub Actions**

> Deployed a containerized AI sales-forecasting application to AWS EC2 with HTTPS, pushed versioned images to Amazon ECR, verified private S3 access with IAM, and configured repeatable Kubernetes kind deployments and CI smoke tests.
