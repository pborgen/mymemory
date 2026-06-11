resource "aws_secretsmanager_secret" "postgres_url" {
  name_prefix = "${var.app_name}/postgres-url-"
  description = "POSTGRES_URL for the MyMemory app"
}

resource "aws_secretsmanager_secret_version" "postgres_url" {
  secret_id     = aws_secretsmanager_secret.postgres_url.id
  secret_string = local.postgres_url
}

# Note: generation (Claude) and embeddings (Titan) both run on AWS Bedrock,
# IAM-authenticated through the App Runner instance role — no API key secret.
