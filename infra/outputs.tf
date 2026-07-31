output "app_url" {
  description = "Public HTTPS URL of the App Runner service"
  value       = "https://${aws_apprunner_service.main.service_url}"
}

output "ecr_repository_url" {
  description = "ECR repository to push the Docker image to"
  value       = aws_ecr_repository.api.repository_url
}

output "rds_endpoint" {
  description = "RDS Postgres endpoint (private)"
  value       = aws_db_instance.main.address
}

output "db_password" {
  description = "Generated DB master password (empty if you supplied one)"
  value       = var.db_password == "" ? random_password.db[0].result : "(provided via tfvars)"
  sensitive   = true
}

output "github_actions_role_arn" {
  description = "Role ARN for the GitHub Actions deploy workflow (set as repo variable AWS_DEPLOY_ROLE_ARN)"
  value       = aws_iam_role.github_deploy.arn
}

output "apprunner_service_arn" {
  description = "App Runner service ARN (for apprunner:StartDeployment in CI)"
  value       = aws_apprunner_service.main.arn
}

output "llm_backend" {
  description = "Active LLM profile: bedrock | home_gpu"
  value       = var.llm_backend
}

output "need_nat" {
  description = "True when NAT is enabled (home_gpu and/or google_client_id)"
  value       = local.need_nat
}

output "home_gpu_api_key" {
  description = "Bearer for Caddy on the GPU box (only when llm_backend=home_gpu)"
  value       = local.use_home_gpu ? local.home_gpu_api_key_effective : ""
  sensitive   = true
}
