# Kubernetes (kind)

This is how I run Forecast in a local Kubernetes cluster using [kind](https://kind.sigs.k8s.io/). The public website runs directly in Docker on AWS EC2, not on Kubernetes or EKS.

You'll need Docker, kind, and kubectl installed.

## Start a cluster

From the repository root:

```bash
docker build -t forecastops-ai:local .
kind create cluster --name forecastops
kind load docker-image forecastops-ai:local --name forecastops
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl rollout status deployment/forecastops-ai --timeout=180s
kubectl get pods -l app=forecastops-ai
kubectl port-forward service/forecastops-ai 8000:8000
```

In another terminal:

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

You should get `{"status":"ok"}`.

To look at what Kubernetes started:

```bash
kubectl describe deployment/forecastops-ai
kubectl logs deployment/forecastops-ai
```

When you're finished:

```bash
kind delete cluster --name forecastops
```

## GitHub Actions

The [Kubernetes smoke-test workflow](../.github/workflows/kubernetes-smoke.yml) builds the Docker image, creates a temporary kind cluster, applies these same manifests, and checks the health endpoint.

[Here's a successful run from November 5, 2026](https://github.com/jeshwanthanthony/forecastops-ai/actions/runs/41956496746). It tested commit `797604fd`, not every subsequent code change.

## A couple of limits

The manifest starts one replica and uses health probes. For this local test I use synthetic data, with no production Square credentials.

Square connections currently rely on per-process state and local SQLite storage. This kind setup isn't ready to run multiple replicas with real seller sessions. The `t3.micro` EC2 machine is also too small to host a Kubernetes control plane alongside the live app.

AWS setup details are in [AWS.md](../AWS.md).
