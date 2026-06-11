# infra — AWS deployment (App Runner + RDS/pgvector + Bedrock)

Deploys the Python `apps/api` backend (FastAPI memory engine) to AWS:

```
ECR  ──image──▶  App Runner  ──VPC connector──▶  RDS Postgres 16 + pgvector (private)
                     │
                     ├── instance role ──▶  Bedrock (Claude generation + Titan embeddings)
                     └── instance role ──▶  Secrets Manager (POSTGRES_URL)

GitHub Actions ──OIDC──▶ assume mymemory-github-deploy ──▶ push image to ECR
```

- **Compute:** App Runner pulls the image from ECR and auto-redeploys on each push.
- **DB:** RDS Postgres 16 (`db.t4g.micro`), private — only the App Runner VPC
  connector can reach it. The app runs `CREATE EXTENSION IF NOT EXISTS vector`
  and creates the `memories`/`memory_chat_history` tables on first boot.
- **AI:** Claude (answer generation) + Amazon Titan (embeddings) on Bedrock,
  authenticated by the App Runner **instance role** (no API keys). Traffic reaches
  Bedrock over a PrivateLink interface endpoint (no NAT, DB stays private).
- **CI/CD:** GitHub Actions deploys keylessly via an OIDC-assumed IAM role.

## Prerequisites (one-time)

1. AWS credentials with admin-ish rights (`aws sts get-caller-identity` works).
2. **Enable Bedrock model access** in your region (Bedrock console → *Model
   access*) for BOTH:
   - the Claude model in `rag_model_id` (default Claude Haiku 4.5), and
   - **Amazon Titan Text Embeddings v2** (`amazon.titan-embed-text-v2:0`).

   Without this the engine gets `AccessDenied` even though the IAM policy is
   correct. (Some accounts must also submit the Anthropic "use case details"
   form before Claude calls succeed.)
3. Docker running locally (the image builds `linux/amd64`).

## Deploy (from a laptop)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # edit: github_repo, google_client_id (optional)
./deploy.sh
```

`deploy.sh` will: `terraform init` + create ECR → build/push the image →
`terraform apply` the full stack → print the public `app_url`.

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

- `github_repo` — `owner/name` allowed to assume the deploy role.
- `google_client_id` — enable Google OAuth (blank disables it).
- `allow_dev_auth_headers` — keep `"false"` in prod (the `x-user-email` bypass).
- `db_password` — leave blank to auto-generate.
- `rag_model_id` / `embed_model_id` — Bedrock model ids.
- sizing: `apprunner_cpu` / `apprunner_memory`, `db_instance_class`.

## Outputs

- `app_url` — public HTTPS URL of the service.
- `rds_endpoint` — private DB host.
- `db_password` — generated master password (`terraform output -raw db_password`).
- `github_actions_role_arn` — role ARN for CI deploys.
- `apprunner_service_arn` — for an explicit `apprunner:StartDeployment` if needed.
