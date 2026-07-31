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
