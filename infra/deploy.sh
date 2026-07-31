#!/usr/bin/env bash
# Build, push, and deploy the MyMemory API to AWS App Runner (low-cost path).
#
#   API  (FastAPI)  -> App Runner + RDS + Bedrock (or home_gpu tunnel)
#   Web  (Next.js)  -> Vercel (default). Set deploy_web_on_apprunner=true to
#                     also keep an App Runner web service.
#
# Usage:  ./deploy.sh
set -euo pipefail

cd "$(dirname "$0")"
REPO_ROOT="$(cd .. && pwd)"
TAG="${IMAGE_TAG:-latest}"

echo "==> terraform init"
terraform init -input=false

echo "==> ensuring API ECR repository exists"
terraform apply -input=false -auto-approve -target=aws_ecr_repository.api

API_ECR="$(terraform output -raw ecr_repository_url)"
REGISTRY="${API_ECR%%/*}"
REGION="${AWS_REGION:-$(echo "$REGISTRY" | cut -d. -f4)}"

echo "==> docker login to $REGISTRY"
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> building API image ${API_ECR}:${TAG}"
docker build --platform linux/amd64 \
  -f "$REPO_ROOT/apps/api/Dockerfile" \
  -t "${API_ECR}:${TAG}" \
  -t "${API_ECR}:latest" \
  "$REPO_ROOT"
docker push "${API_ECR}:${TAG}"
docker push "${API_ECR}:latest"

echo "==> terraform apply (full stack)"
terraform apply -input=false -auto-approve

echo
echo "==> Done (low-cost API-only path)."
echo "API:  $(terraform output -raw app_url)"
WEB_URL="$(terraform output -raw web_url 2>/dev/null || true)"
if [ -n "${WEB_URL}" ]; then
  echo "Web:  $WEB_URL"
else
  echo "Web:  (App Runner web off — deploy apps/web to Vercel; see DOMAINS.md)"
fi
echo "LLM:  $(terraform output -raw llm_backend)"
echo
