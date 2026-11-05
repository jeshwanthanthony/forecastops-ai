# Deployment notes

I use two setups for Forecast: Docker on AWS EC2 for the website, and Kubernetes kind for local testing. They're separate on purpose.

## AWS

Checked on November 4–5, 2026:

| What | What I tested |
| --- | --- |
| EC2 | Amazon Linux 2023 on \`t3.micro\`, \`us-east-2\`, instance \`i-00b40ccf59a49fe38\` |
| HTTPS | https://forecastops.jeshwanthanthony.com behind Nginx and a Certbot certificate |
| IAM | Instance role \`ForecastOps-EC2-ECR-Role\`, without saved AWS access keys |
| ECR | Pushed private image \`forecastops-ai:v1\` |
| S3 | Uploaded a test file under \`reports/test.txt\` in a private bucket |
| Docker | Later deployed \`forecastops-release:ba39344\` on localhost port \`8004\` |
| API | Public \`/api/health\`, \`/api/demo\`, and \`/api/square/status\` returned HTTP 200 after that deployment |

The image pushed to ECR is not the same as the latest manually transferred Docker image. ECR publishing and deployment are not connected automatically.

I kept these output snippets from the original EC2 tests:

\`\`\`text
arn:aws:sts::264632269822:assumed-role/ForecastOps-EC2-ECR-Role/i-00b40ccf59a49fe38

v1: digest: sha256:0ac4d78739fa62eba07f526ed0ddd08a68eca6ddf3d09e1926706b4526602842 size: 2204

upload: ../../tmp/forecastops-s3-test.txt to s3://forecastops-ai-reports-264632269822-us-east-2-an/reports/test.txt
\`\`\`

The S3 upload checked permissions and private storage. Forecast doesn't save reports to S3 yet.

To check the same resources from EC2:

\`\`\`bash
aws sts get-caller-identity
aws ecr describe-images --region us-east-2 --repository-name forecastops-ai --image-ids imageTag=v1
aws s3api head-object --bucket forecastops-ai-reports-264632269822-us-east-2-an --key reports/test.txt
curl -fsS https://forecastops.jeshwanthanthony.com/api/health
\`\`\`

## Square

Square Production OAuth was connected successfully and one real import produced a forecast from 180 daily sales observations. That was before the latest UI release. Release \`ba39344\` passed the public health, demo, and Square-configuration endpoint checks; a new end-to-end import on that specific release wasn't part of those checks.

The resulting sales figures are estimates, not reconciled Square accounting totals. More sellers, session isolation, and error paths still need checking before treating this as a multi-merchant service.

## Kubernetes

The Kubernetes files are [deployment.yaml](../k8s/deployment.yaml), [service.yaml](../k8s/service.yaml), and the [kind setup instructions](../k8s/README.md).

The [kind smoke test passed](https://github.com/jeshwanthanthony/forecastops-ai/actions/runs/41956496746) on November 5, 2026, for commit \`797604fd\`. GitHub Actions built the image, started a temporary kind cluster, applied the manifests, and checked the application's health endpoint.

That proves the workflow ran successfully for that commit. It doesn't mean the public website runs on Kubernetes or that later feature-branch changes have passed the same smoke test.

## Still manual

There isn't an automatic GitHub-to-AWS deployment pipeline yet. Docker images have been built and tested locally, copied to EC2, then switched behind Nginx after checking the replacement container. The older container is kept for rollback.

No EKS cluster, no automatic ECR-based release, and no application report storage in S3. That's the current scope.
