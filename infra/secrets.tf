resource "aws_secretsmanager_secret" "postgres_url" {
  name_prefix = "${var.app_name}/postgres-url-"
  description = "POSTGRES_URL for the MyMemory app"
}

resource "aws_secretsmanager_secret_version" "postgres_url" {
  secret_id     = aws_secretsmanager_secret.postgres_url.id
  secret_string = local.postgres_url
}

# Note: when llm_backend=bedrock, generation + embeddings use IAM (instance
# role) — no model API key secret. when llm_backend=home_gpu, OPENAI_API_KEY /
# EMBED_API_KEY are injected from aws_secretsmanager_secret.home_gpu_api_key.

locals {
  langfuse_enabled = trimspace(var.langfuse_public_key) != "" && trimspace(var.langfuse_secret_key) != ""
}

resource "aws_secretsmanager_secret" "langfuse_public_key" {
  count       = local.langfuse_enabled ? 1 : 0
  name_prefix = "${var.app_name}/langfuse-public-"
  description = "LANGFUSE_PUBLIC_KEY for MyMemory"
}

resource "aws_secretsmanager_secret_version" "langfuse_public_key" {
  count         = local.langfuse_enabled ? 1 : 0
  secret_id     = aws_secretsmanager_secret.langfuse_public_key[0].id
  secret_string = var.langfuse_public_key
}

resource "aws_secretsmanager_secret" "langfuse_secret_key" {
  count       = local.langfuse_enabled ? 1 : 0
  name_prefix = "${var.app_name}/langfuse-secret-"
  description = "LANGFUSE_SECRET_KEY for MyMemory"
}

resource "aws_secretsmanager_secret_version" "langfuse_secret_key" {
  count         = local.langfuse_enabled ? 1 : 0
  secret_id     = aws_secretsmanager_secret.langfuse_secret_key[0].id
  secret_string = var.langfuse_secret_key
}
