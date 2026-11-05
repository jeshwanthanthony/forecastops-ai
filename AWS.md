# AWS notes

The public site runs on a small EC2 instance in Ohio. Nginx handles HTTPS, then passes requests to a FastAPI app in Docker. The Kubernetes files in this repository are for a separate kind setup, not the live server.

## Server

- EC2: Amazon Linux 2023, \`t3.micro\`, \`us-east-2\`
- Instance: \`i-00b40ccf59a49fe38\`
- Website: https://forecastops.jeshwanthanthony.com
- IAM role: \`ForecastOps-EC2-ECR-Role\`

As of November 5, 2026, the live release is \`forecastops-release:ba39344\` on localhost port \`8004\`, behind Nginx. The previous \`forecastops-final-square\` container on port \`8003\` was left available for rollback. These are deployment details, not fixed ports in the app.

\`\`\`text
Browser
  -> HTTPS / Nginx on EC2
  -> Docker / FastAPI
  -> React frontend and Python forecast API
\`\`\`

The instance is small, so I build the Docker image on my PC and copy it to EC2 rather than running a heavy build on the server.

## ECR and S3

I also tested two AWS services outside the app:

- **ECR:** pushed \`forecastops-ai:v1\` to a private repository in \`us-east-2\`.
- **S3:** uploaded a test file to the private \`reports/\` prefix using the EC2 IAM role.

The app does **not** currently pull from ECR as part of an automatic deployment, and it doesn't write forecast files to S3. The commands and original output are in [deployment notes](docs/DEPLOYMENT_EVIDENCE.md).

## Check the server

These commands only inspect things:

\`\`\`bash
sudo docker ps
sudo nginx -t
curl -fsS https://forecastops.jeshwanthanthony.com/api/health
aws sts get-caller-identity
aws ecr describe-images --region us-east-2 --repository-name forecastops-ai --image-ids imageTag=v1
aws s3api head-object --bucket forecastops-ai-reports-264632269822-us-east-2-an --key reports/test.txt
\`\`\`

Images are still deployed manually. Pushing to GitHub or ECR by itself doesn't replace the running container. I keep the last working container and an Nginx config backup until the new release passes public health and demo checks.

## Kubernetes

The manifests in [k8s](k8s/README.md) run the same application in a local kind cluster. The [GitHub Actions smoke test](https://github.com/jeshwanthanthony/forecastops-ai/actions/runs/41956496746) passed on November 5, 2026. There is no EKS cluster here.

Running a Kubernetes control plane alongside the app on a \`t3.micro\` would add complexity and memory pressure without helping this project.

## Square and access

Production Square credentials stay in a restricted environment file on EC2, not in Docker images or Git. Encrypted connection data is stored on a restricted volume. Be careful with OAuth callback logs, proxy headers, and access to the SQLite database.

One real Square import worked on the earlier deployed release. The newer release passed health, demo, and Square configuration checks, but that doesn't replace checking a real seller import and session isolation.

EC2, its public IPv4 address, EBS, ECR, and S3 can all incur charges. AWS budget alerts aren't spending caps.
