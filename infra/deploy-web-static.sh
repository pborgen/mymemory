#!/usr/bin/env bash
# Build the static Next.js export and sync it to S3 + invalidate CloudFront.
#
# Prerequisites:
#   - infra terraform applied (web_static.tf)
#   - AWS credentials
#   - Node 20+
#
# Usage (from repo root or infra/):
#   NEXT_PUBLIC_API_URL=https://gapyciuy6q.us-east-1.awsapprunner.com \
#     ./infra/deploy-web-static.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INFRA="$ROOT/infra"
WEB="$ROOT/apps/web"

if [ -z "${NEXT_PUBLIC_API_URL:-}" ]; then
  echo "Set NEXT_PUBLIC_API_URL to the public API HTTPS URL (no trailing slash)." >&2
  exit 1
fi

SITE_URL="${NEXT_PUBLIC_SITE_URL:-}"
if [ -z "$SITE_URL" ]; then
  SITE_URL="https://$(cd "$INFRA" && terraform output -raw web_cloudfront_domain)"
fi

BUCKET="$(cd "$INFRA" && terraform output -raw web_bucket)"
DIST_ID="$(cd "$INFRA" && terraform output -raw web_cloudfront_distribution_id)"
REGION="${AWS_REGION:-us-east-1}"

echo "==> Building static export (API=$NEXT_PUBLIC_API_URL SITE=$SITE_URL)"
cd "$WEB"
npm install --silent
NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" \
NEXT_PUBLIC_SITE_URL="$SITE_URL" \
  npm run build

if [ ! -d "$WEB/out" ]; then
  echo "Missing $WEB/out — next build did not produce a static export." >&2
  exit 1
fi
# Friendly 404 for CloudFront custom error responses.
if [ ! -f "$WEB/out/404.html" ] && [ -f "$WEB/out/404/index.html" ]; then
  cp "$WEB/out/404/index.html" "$WEB/out/404.html"
elif [ ! -f "$WEB/out/404.html" ]; then
  cp "$WEB/out/index.html" "$WEB/out/404.html"
fi

echo "==> Syncing to s3://$BUCKET"
aws s3 sync "$WEB/out/" "s3://$BUCKET/" --delete --region "$REGION" \
  --cache-control "public,max-age=300" \
  --exclude "*.html"
aws s3 sync "$WEB/out/" "s3://$BUCKET/" --region "$REGION" \
  --exclude "*" --include "*.html" \
  --cache-control "public,max-age=60" \
  --content-type "text/html; charset=utf-8"

echo "==> Invalidating CloudFront $DIST_ID"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" \
  --query 'Invalidation.Id' --output text

echo
echo "Web: $(cd "$INFRA" && terraform output -raw web_url)"
echo "Done."
