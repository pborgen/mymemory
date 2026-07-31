variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "mymemory"
}

variable "image_tag" {
  description = "ECR image tag App Runner deploys"
  type        = string
  default     = "latest"
}

# ── Application secrets / config ──────────────────────────

variable "llm_backend" {
  description = "Where generation + embeddings run: bedrock | home_gpu"
  type        = string
  default     = "bedrock"

  validation {
    condition     = contains(["bedrock", "home_gpu"], var.llm_backend)
    error_message = "llm_backend must be \"bedrock\" or \"home_gpu\"."
  }
}

# Bedrock (llm_backend = bedrock) — IAM via App Runner instance role, no API keys.
variable "rag_model_id" {
  description = "Bedrock model id (inference profile) for answer generation"
  type        = string
  default     = "us.amazon.nova-2-lite-v1:0"
}

variable "embed_model_id" {
  description = "Bedrock embedding model id (must output EMBED_DIM-wide vectors)"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

# Home GPU via Cloudflare Tunnel (llm_backend = home_gpu) → Tailscale box 100.99.15.47
variable "home_gpu_openai_base_url" {
  description = "OpenAI-compatible base URL for vLLM behind the tunnel (must end with /v1)"
  type        = string
  default     = ""
}

variable "home_gpu_chat_model" {
  description = "Chat model id served by vLLM on the GPU box"
  type        = string
  default     = "Qwen/Qwen2.5-0.5B-Instruct"
}

variable "home_gpu_embed_base_url" {
  description = "Ollama base URL behind the tunnel (root, no /v1)"
  type        = string
  default     = ""
}

variable "home_gpu_embed_model" {
  description = "Ollama embedding model (must match VECTOR dim)"
  type        = string
  default     = "mxbai-embed-large"
}

variable "home_gpu_embed_dim" {
  description = "Embedding vector size (must match DB VECTOR(n))"
  type        = number
  default     = 1024
}

variable "home_gpu_api_key" {
  description = "Bearer token for the home-GPU Caddy proxy; blank → auto-generate"
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_client_id" {
  description = "Google OAuth client ID (required in production — blank refuses boot). Non-empty also enables NAT so App Runner can fetch Google signing certs."
  type        = string
  default     = ""
}

variable "allow_dev_auth_headers" {
  description = "Enable the x-user-email dev auth bypass (MUST stay false in prod)"
  type        = string
  default     = "false"
}

variable "super_admin_email" {
  description = "Bootstrap admin email seeded on API startup (your Google account)"
  type        = string
  default     = ""
}

variable "cors_origins" {
  description = "Comma-separated browser origins allowed to call the API (web App Runner URL, custom domain)"
  type        = string
  default     = ""
}

variable "rate_limit_chat_per_min" {
  description = "Per-user rolling-minute cap on POST /api/memory/chat"
  type        = number
  default     = 30
}

variable "rate_limit_store_per_min" {
  description = "Per-user rolling-minute cap on POST /api/memory"
  type        = number
  default     = 20
}

# ── Database ──────────────────────────────────────────────
variable "db_name" {
  description = "Initial database name"
  type        = string
  default     = "mymemory"
}

variable "db_username" {
  description = "Master username for RDS"
  type        = string
  default     = "mymemory_admin"
}

variable "db_password" {
  description = "Master password for RDS (auto-generated if left blank)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS storage in GB"
  type        = number
  default     = 20
}

variable "db_backup_retention_days" {
  description = "RDS automated backup retention (1 is cheapest; 0 disables)"
  type        = number
  default     = 1
}

# ── App Runner sizing ─────────────────────────────────────
variable "app_environment" {
  description = "API ENVIRONMENT env var. Use \"production\" only with Google OAuth + locked CORS (boot guard). \"staging\" for low-cost personal deploys."
  type        = string
  default     = "staging"
}

variable "apprunner_cpu" {
  description = "App Runner vCPU (256 is cheapest)"
  type        = string
  default     = "256"
}

variable "apprunner_memory" {
  description = "App Runner memory in MB (512 pairs with 256 vCPU)"
  type        = string
  default     = "512"
}

# ── GitHub Actions OIDC (keyless deploy) ──────────────────
variable "github_repo" {
  description = "GitHub repo allowed to assume the deploy role, as owner/name"
  type        = string
  default     = "pborgen/mymemory"
}
