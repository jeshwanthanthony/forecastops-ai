# ForecastOps AI on Kubernetes (kind)

The live website runs Docker on AWS EC2. These manifests deploy the **same application** to a disposable local kind Kubernetes cluster or a kind cluster created by GitHub Actions. They are **not an AWS EKS deployment**.

## Run locally

Requires Docker, kind, kubectl, and this repository. From the repository root:

```bash
docker build -t forecastops-ai:local .
kind create cluster --name forecastops
kind load docker-image forecastops-ai:local --name forecastops
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl rollout status deployment/forecastops-ai --timeout=180s
kubectl get pods -l app=forecastops-ai
kubectl get service forecastops-ai
kubectl port-forward service/forecastops-ai 8000:8000
```

From a second terminal:

```bash
curl --fail http://127.0.0.1:8000/api/health
```

Expected health payload: `{"status":"ok"}`. To test a rolling update or resilience, inspect `kubectl describe deployment/forecastops-ai` and `kubectl logs deployment/forecastops-ai`.

Clean up the local test:

```bash
kind delete cluster --name forecastops
```

## GitHub Actions proof

See [Kubernetes smoke workflow](../.github/workflows/kubernetes-smoke.yml) and the repository's **Actions** tab. It builds the image, creates a kind cluster, loads the image, deploys the manifests, waits for readiness, and checks `/api/health`.

A successful run is stronger evidence than YAML files alone. A workflow file by itself does not establish that the test passed.

## Boundaries

- One replica by default. Readiness/liveness probes hit `/api/health`.
- This local demo uses the synthetic forecast with no Square/OpenAI production credentials.
- Square OAuth tokens currently use local SQLite storage; do not scale to multiple replicas or connect production sellers in ephemeral kind without a durable external token/session design.
- The live AWS EC2 `t3.micro` is too small for a reliable always-on Kubernetes server alongside this application. Do not install kind/K3s there solely for a resume keyword.

For actual AWS setup and proof, see [deployment evidence](../docs/DEPLOYMENT_EVIDENCE.md).
