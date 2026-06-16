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
# Generation + embeddings both run on AWS Bedrock (IAM auth via the App Runner
# instance role), so no Anthropic / embedding API key is required.

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

variable "google_client_id" {
  description = "Google OAuth client ID (optional; blank disables Google login)"
  type        = string
  default     = ""
}

variable "allow_dev_auth_headers" {
  description = "Enable the x-user-email dev auth bypass (keep false in prod)"
  type        = string
  default     = "false"
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

# ── App Runner sizing ─────────────────────────────────────
variable "apprunner_cpu" {
  description = "App Runner vCPU (e.g. 256, 512, 1024)"
  type        = string
  default     = "512"
}

variable "apprunner_memory" {
  description = "App Runner memory in MB (e.g. 512, 1024, 2048)"
  type        = string
  default     = "1024"
}

# ── GitHub Actions OIDC (keyless deploy) ──────────────────
variable "github_repo" {
  description = "GitHub repo allowed to assume the deploy role, as owner/name"
  type        = string
  default     = "pborgen/mymemory"
}
