# AWS deployment: current architecture and verification

This project has a **running Docker-on-EC2 deployment**. It also has a separate local Kubernetes kind deployment; **EKS and K3s are not running in AWS**.

## Architecture

```text
Browser -> forecastops.jeshwanthanthony.com (HTTPS)
        -> AWS EC2 (us-east-2, t3.micro, Amazon Linux 2023)
        -> Nginx :443 -> Docker container 127.0.0.1:8000
        -> FastAPI serves React app + prediction API

EC2 IAM instance role
        -> AWS ECR (Docker image v1 pushed)
        -> AWS S3 (restricted reports/ prefix; test upload verified)

Local PC or GitHub Actions
        -> kind (Kubernetes in Docker)
        -> Deployment + Service + health probes
```

The ECR push and S3 write were **verified using the EC2 terminal**. The live EC2 container currently runs a locally built image; there is not yet an ECR-driven deployment pipeline. S3 integration in the application is not yet implemented. See [recorded evidence](docs/DEPLOYMENT_EVIDENCE.md).

## Resources

| Resource | Configuration |
| --- | --- |
| AWS region | `us-east-2` (Ohio) |
| EC2 instance | `i-00b40ccf59a49fe38`, Amazon Linux 2023, `t3.micro` |
| EC2 instance role | `ForecastOps-EC2-ECR-Role`, attached instance profile |
| Private ECR repository | `264632269822.dkr.ecr.us-east-2.amazonaws.com/forecastops-ai` |
| ECR image | `v1` with digest `sha256:0ac4d78739fa62eba07f526ed0ddd08a68eca6ddf3d09e1926706b4526602842` |
| Private S3 bucket | `forecastops-ai-reports-264632269822-us-east-2-an` |
| S3 access | EC2 role scoped to `reports/`, with `ListBucket`, `GetObject`, `PutObject` |
| Public site | [https://forecastops.jeshwanthanthony.com](https://forecastops.jeshwanthanthony.com) |

S3 has public access blocked, ACLs disabled, and SSE-S3 encryption. Never upload real sellers' Square data before implementing proper tenant-specific authorization, retention rules, and secure report access.

## Read-only verification from the EC2 terminal

```bash
aws sts get-caller-identity
aws ecr describe-images --region us-east-2 --repository-name forecastops-ai --image-ids imageTag=v1
aws s3api head-object --bucket forecastops-ai-reports-264632269822-us-east-2-an --key reports/test.txt
sudo docker ps
curl --fail --silent --show-error http://127.0.0.1:8000/api/health
```

If access to a service is denied, inspect its IAM policies rather than creating permanent AWS access keys on the server.

## Rebuild and publish an updated image

Only after tests pass and a deployment change is approved, from the source directory on EC2:

```bash
sudo docker build -t forecastops-ai:local .
aws ecr get-login-password --region us-east-2 | sudo docker login --username AWS --password-stdin 264632269822.dkr.ecr.us-east-2.amazonaws.com
sudo docker tag forecastops-ai:local 264632269822.dkr.ecr.us-east-2.amazonaws.com/forecastops-ai:VERSION
sudo docker push 264632269822.dkr.ecr.us-east-2.amazonaws.com/forecastops-ai:VERSION
```

Replace `VERSION` with a new immutable version tag, for example the release version or commit SHA; do not overwrite historical tags. **Pushing to ECR does not update the running EC2 container.** Separately plan a deployment and rollback when ready. Never paste your Square Application Secret or personal access token into CI or the repository.

## Kubernetes

`k8s/deployment.yaml` and `k8s/service.yaml` describe a local kind test environment. See [kind deployment instructions](k8s/README.md). The GitHub Actions workflow exercises the same manifests on an ephemeral runner and checks the health endpoint; see the Actions tab for success or failure.

A single-node Kubernetes control plane alongside the app is not recommended on the current 1 GiB EC2 instance. The portfolio project **does not use AWS EKS** and does not require it.

## Cost and safety

AWS promotional credits are finite, and a budget alert is not a hard spending limit. The public IPv4 address, EC2 compute, EBS storage, ECR storage, and S3 usage can incur charges. Keep the image registry private and rotate secrets if exposure is suspected.

The Square Production OAuth deployment is separate from AWS proof. Do not allow real sellers to connect until the authorization flow, storage, access control, and logging are independently verified.
