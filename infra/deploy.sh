#!/usr/bin/env bash
# Build, push, and deploy the MyMemory API to AWS App Runner.
#
# First run provisions everything (ECR, RDS, secrets, IAM, App Runner, the
# GitHub OIDC deploy role). Later runs just rebuild the image and push —
# App Runner auto-redeploys.
#
# Usage:  ./deploy.sh
set -euo pipefail

cd "$(dirname "$0")"
REPO_ROOT="$(cd .. && pwd)"
TAG="${IMAGE_TAG:-latest}"

echo "==> terraform init"
terraform init -input=false

# 1. Create the ECR repo first so we have somewhere to push.
echo "==> ensuring ECR repository exists"
terraform apply -input=false -auto-approve -target=aws_ecr_repository.api

ECR_URL="$(terraform output -raw ecr_repository_url)"
REGISTRY="${ECR_URL%%/*}"
# ECR URL looks like <acct>.dkr.ecr.<region>.amazonaws.com/<repo>
REGION="${AWS_REGION:-$(echo "$REGISTRY" | cut -d. -f4)}"

# 2. Build (linux/amd64 for App Runner) and push the image.
echo "==> docker login to $REGISTRY"
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> building image $ECR_URL:$TAG"
docker build --platform linux/amd64 \
  -f "$REPO_ROOT/apps/api/Dockerfile" \
  -t "$ECR_URL:$TAG" "$REPO_ROOT"

echo "==> pushing image"
docker push "$ECR_URL:$TAG"

# 3. Apply the rest of the stack (RDS, secrets, IAM, App Runner).
echo "==> terraform apply (full stack)"
terraform apply -input=false -auto-approve

echo
echo "==> Done. App URL:"
terraform output -raw app_url
echo
