#!/usr/bin/env bash
# Build, push, and deploy the MyMemory stack to AWS App Runner.
#
#   API  (FastAPI)  -> App Runner (private VPC egress -> RDS/pgvector + Bedrock)
#   Web  (Next.js)  -> App Runner (public; browser calls the API directly)
#
# The web client inlines NEXT_PUBLIC_API_URL at build time, so the API must be
# deployed first to learn its public URL before the web image is built.
#
# Usage:  ./deploy.sh
set -euo pipefail

cd "$(dirname "$0")"
REPO_ROOT="$(cd .. && pwd)"
TAG="${IMAGE_TAG:-latest}"

echo "==> terraform init"
terraform init -input=false

# 1. Create both ECR repos first so we have somewhere to push.
echo "==> ensuring ECR repositories exist"
terraform apply -input=false -auto-approve \
  -target=aws_ecr_repository.api -target=aws_ecr_repository.web

API_ECR="$(terraform output -raw ecr_repository_url)"
WEB_ECR="$(terraform output -raw web_ecr_repository_url)"
REGISTRY="${API_ECR%%/*}"
REGION="${AWS_REGION:-$(echo "$REGISTRY" | cut -d. -f4)}"

echo "==> docker login to $REGISTRY"
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

# 2. Build + push the API image.
echo "==> building API image $API_ECR:$TAG"
docker build --platform linux/amd64 \
  -f "$REPO_ROOT/apps/api/Dockerfile" \
  -t "$API_ECR:$TAG" "$REPO_ROOT"
docker push "$API_ECR:$TAG"

# 3. Bring up the API service (and its deps: RDS, secrets, IAM, connector,
#    endpoints) so we can read its public URL.
echo "==> terraform apply (API service + dependencies)"
terraform apply -input=false -auto-approve -target=aws_apprunner_service.main

API_URL="$(terraform output -raw app_url)"
echo "==> API is at $API_URL"

# 4. Build + push the web image with the API URL baked in.
echo "==> building web image $WEB_ECR:$TAG (NEXT_PUBLIC_API_URL=$API_URL)"
docker build --platform linux/amd64 \
  -f "$REPO_ROOT/apps/web/Dockerfile" \
  --build-arg "NEXT_PUBLIC_API_URL=$API_URL" \
  -t "$WEB_ECR:$TAG" "$REPO_ROOT"
docker push "$WEB_ECR:$TAG"

# 5. Apply the full stack (creates the web App Runner service now its image exists).
echo "==> terraform apply (full stack incl. web)"
terraform apply -input=false -auto-approve

echo
echo "==> Done."
echo "API: $(terraform output -raw app_url)"
echo "Web: $(terraform output -raw web_url)"
echo
