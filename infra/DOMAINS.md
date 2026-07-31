# Static web on S3 + CloudFront (Next.js `output: "export"`)
#
# Hostnames (recommended)
# ───────────────────────
#   https://memory.informedbydata.com     → CloudFront → S3 (this file)
#   https://api.memory.informedbydata.com → App Runner API
#
# Cost: typically well under $1–3/mo for light personal traffic (S3 storage +
# CloudFront PriceClass_100). No always-on Node server.
#
# ── 1. Build + deploy static files ──
#
#   cd infra && terraform apply   # creates bucket + CloudFront
#
#   NEXT_PUBLIC_API_URL=https://gapyciuy6q.us-east-1.awsapprunner.com \
#     ./deploy-web-static.sh
#
# Open the URL from:
#   terraform output -raw web_url
#
# ── 2. Custom domain (GoDaddy + ACM) ──
#
# CloudFront requires the certificate in **us-east-1**:
#
#   1. ACM (N. Virginia) → Request public cert for memory.informedbydata.com
#   2. Add the DNS validation CNAME at GoDaddy
#   3. terraform.tfvars:
#        web_custom_domain         = "memory.informedbydata.com"
#        web_acm_certificate_arn   = "arn:aws:acm:us-east-1:…:certificate/…"
#        cors_origins              = "https://memory.informedbydata.com"
#        api_custom_domain         = "api.memory.informedbydata.com"  # optional
#   4. terraform apply
#   5. GoDaddy CNAME:
#        Host: memory
#        Points to: <CloudFront domain from terraform output web_cloudfront_domain>
#           e.g. d111111abcdef8.cloudfront.net
#
# ── 3. API CORS ──
#
# Browser origin must be allowed once you leave staging open-CORS:
#
#   cors_origins = "https://memory.informedbydata.com"
#   # or temporarily: https://xxxx.cloudfront.net
#
# ── 4. Local static preview ──
#
#   cd apps/web
#   NEXT_PUBLIC_API_URL=http://localhost:8080 npm run build
#   npm start   # serves ./out on :3000
