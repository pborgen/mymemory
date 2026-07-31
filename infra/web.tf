# ── Web frontend on App Runner (optional) ─────────────────
# Preferred prod path is Vercel at memory.informedbydata.com — see DOMAINS.md.
# Set deploy_web_on_apprunner = true only if you still want this service.

resource "aws_ecr_repository" "web" {
  count                = var.deploy_web_on_apprunner ? 1 : 0
  name                 = "${var.app_name}-web"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "web" {
  count      = var.deploy_web_on_apprunner ? 1 : 0
  repository = aws_ecr_repository.web[0].name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images older than 14 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_apprunner_service" "web" {
  count        = var.deploy_web_on_apprunner ? 1 : 0
  service_name = "${var.app_name}-web"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }
    auto_deployments_enabled = true

    image_repository {
      image_identifier      = "${aws_ecr_repository.web[0].repository_url}:${var.image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "3000"
        runtime_environment_variables = {
          PORT     = "3000"
          HOSTNAME = "0.0.0.0"
        }
      }
    }
  }

  instance_configuration {
    cpu    = var.apprunner_cpu
    memory = var.apprunner_memory
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }
}

output "web_apprunner_url" {
  description = "App Runner web URL (empty when deploy_web_on_apprunner=false)"
  value       = var.deploy_web_on_apprunner ? "https://${aws_apprunner_service.web[0].service_url}" : ""
}

output "web_ecr_repository_url" {
  description = "ECR repository for the optional App Runner web image"
  value       = var.deploy_web_on_apprunner ? aws_ecr_repository.web[0].repository_url : ""
}
