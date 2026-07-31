# infra — AWS deployment (App Runner + RDS/pgvector + LLM)

Deploys the Python `apps/api` backend (FastAPI memory engine) to AWS:

```
ECR  ──image──▶  App Runner  ──VPC connector──▶  RDS Postgres 16 + pgvector (private)
                     │
                     ├── llm_backend=bedrock  → Bedrock PrivateLink (Nova/Claude + Titan)
                     ├── google_client_id set → NAT → googleapis.com (ID-token certs)
                     └── llm_backend=home_gpu → NAT → Cloudflare Tunnel → home GPU box
                                              (vLLM :8001 + Ollama :11434)

GitHub Actions ──OIDC──▶ assume mymemory-github-deploy ──▶ push image to ECR
```

- **Compute:** App Runner pulls the image from ECR and auto-redeploys on each push.
- **DB:** RDS Postgres 16 (`db.t4g.micro`), private — only the App Runner VPC
  connector subnets can reach it. The app runs `CREATE EXTENSION IF NOT EXISTS vector`
  and creates the `memories`/`memory_chat_history` tables on first boot.
- **AI (pick one via `llm_backend`):**
  - **`bedrock` (default):** Nova/Claude + Titan on Bedrock, IAM via instance
    role, PrivateLink for Bedrock.
  - **`home_gpu`:** vLLM + Ollama on your Tailscale GPU box (`100.99.15.47`),
    exposed with Cloudflare Tunnel + Caddy bearer auth. See
    **`infra/home-gpu/README.md`**.
- **NAT (~$32/mo):** enabled when `llm_backend=home_gpu` **or**
  `google_client_id` is set. App Runner uses VPC-only egress (private RDS);
  Google ID-token verify and home-GPU tunnels both need public HTTPS out.
- **CI/CD:** GitHub Actions deploys keylessly via an OIDC-assumed IAM role.

## Prerequisites (one-time)

1. AWS credentials with admin-ish rights (`aws sts get-caller-identity` works).
2. **If `llm_backend=bedrock`:** enable Bedrock model access in your region for
   BOTH the generation model and **Amazon Titan Text Embeddings v2**.
3. **If `llm_backend=home_gpu`:** Cloudflare account + tunnel DNS routes, and
   Caddy/cloudflared running on the GPU box (`infra/home-gpu/`).
4. Docker running locally (the image builds `linux/amd64`).

## Deploy (from a laptop)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # edit: github_repo, google_client_id, llm_backend, …
./deploy.sh
```

`deploy.sh` will: `terraform init` + create ECR → build/push the image →
`terraform apply` the full stack → print the public `app_url`.

For **home_gpu**, stand up the tunnel **before** (or right after) apply so
chat works once the API is live:

```bash
# on GPU box — see infra/home-gpu/README.md
./run.sh

# then paste tunnel HTTPS URLs into terraform.tfvars and:
terraform apply
terraform output -raw home_gpu_api_key   # → Caddyfile bearer
```

## Deploy (from GitHub Actions)

After the first `./deploy.sh` (which creates the ECR repo + OIDC deploy role):

```bash
terraform output github_actions_role_arn   # -> set as repo variable AWS_DEPLOY_ROLE_ARN
```

In the GitHub repo, add **Settings → Secrets and variables → Actions → Variables**:

- `AWS_DEPLOY_ROLE_ARN` — the role ARN above
- `AWS_REGION` — e.g. `us-east-1`
- `ECR_REPOSITORY` — `mymemory` (the `app_name`)

Then pushes to `main` trigger `.github/workflows/deploy.yml`, which builds and
pushes a new image; App Runner auto-redeploys (`auto_deployments_enabled`).

## Config (`terraform.tfvars`)

- `llm_backend` — `bedrock` | `home_gpu`
- `home_gpu_openai_base_url` / `home_gpu_embed_base_url` — tunnel HTTPS URLs
  (required when `home_gpu`)
- `home_gpu_api_key` — optional; blank auto-generates (paste into Caddyfile)
- `github_repo` — `owner/name` allowed to assume the deploy role
- `google_client_id` — **required** for a public API; also enables NAT for
  Google cert egress
- `super_admin_email` — your Google email; seeded as admin on startup
- `cors_origins` — comma-separated web origins (required in production);
  CloudFront example: `https://d1x2llv8fpgnu8.cloudfront.net`
- `api_custom_domain` — e.g. `api.memory.informedbydata.com` (see **DOMAINS.md**)
- `deploy_web_on_apprunner` — `false` when the UI is on S3/CloudFront (recommended)
- `allow_dev_auth_headers` — keep `"false"` in prod
- `app_environment` — `production` only with Google + locked CORS; else `staging`
- `rate_limit_chat_per_min` / `rate_limit_store_per_min` — per-user LLM caps
- `db_password` — leave blank to auto-generate
- `rag_model_id` / `embed_model_id` — Bedrock model ids (bedrock profile)
- sizing: `apprunner_cpu` / `apprunner_memory`, `db_instance_class`

App Runner always sets `ENVIRONMENT=production`. Auth stays Google Bearer;
costly chat/store routes are rate-limited per user.

**Custom domains (GoDaddy + Vercel):** see [`DOMAINS.md`](./DOMAINS.md).
**Google Sign-In (prod):** see [`GOOGLE_AUTH.md`](./GOOGLE_AUTH.md).

## Outputs

- `app_url` — public HTTPS URL of the service (App Runner default hostname)
- `api_custom_domain_dns_target` — CNAME target for GoDaddy when using a custom API domain
- `llm_backend` — active profile
- `home_gpu_api_key` — bearer for Caddy (`terraform output -raw home_gpu_api_key`)
- `rds_endpoint` — private DB host
- `db_password` — generated master password
- `github_actions_role_arn` — role ARN for CI deploys
- `apprunner_service_arn` — for an explicit `apprunner:StartDeployment` if needed
