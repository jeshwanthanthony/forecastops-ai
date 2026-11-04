# Optional AWS deployment plan

No resources are provisioned by this repository. EKS control planes and worker nodes incur charges while running; a budget alert does not automatically stop them. Check current prices before proceeding.

Install AWS CLI, Docker, kubectl and eksctl. Configure a dedicated identity with `aws configure` or `aws configure sso`, then confirm it with `aws sts get-caller-identity`. The operator needs permissions to create and delete the chosen EKS cluster, EC2/VPC resources, IAM roles, ECR repository, and optional S3 bucket. Scope the application role separately: `s3:GetObject` and `s3:PutObject` on the specific bucket prefix only; use IRSA or EKS Pod Identity. Do not put AWS keys in the container.

Example commands to run only after choosing a region, unique bucket name, and cost-approved cluster configuration:

```powershell
aws sts get-caller-identity
aws ecr create-repository --repository-name forecastops-ai --region us-east-1
aws s3api create-bucket --bucket REPLACE-WITH-UNIQUE-BUCKET --region us-east-1
eksctl create cluster --name forecastops-demo --region us-east-1 --nodes 1
aws eks update-kubeconfig --name forecastops-demo --region us-east-1
```

Authenticate Docker to ECR using `aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com`, tag and push the tested image to that registry, update the Kubernetes image reference, and apply the manifests. Use a temporary port-forward rather than provisioning a load balancer. Store application secrets in a dedicated secret manager and replace the local SQLite token store before connecting Square across replicas. S3 integration is a plan, not implemented in the app.

After the demonstration, delete resources and verify in the AWS console that none remain:

```powershell
eksctl delete cluster --name forecastops-demo --region us-east-1
aws ecr delete-repository --repository-name forecastops-ai --region us-east-1 --force
```

Empty the chosen S3 bucket only after confirming its contents are disposable, then delete it with `aws s3api delete-bucket --bucket REPLACE-WITH-UNIQUE-BUCKET --region us-east-1`. Check for remaining load balancers, volumes, IP addresses and logs.
