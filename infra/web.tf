# ── Web frontend: Next.js (Node SSR) on App Runner ────────
# A second, public App Runner service serving the Next.js client. It does NOT
# talk to RDS or Bedrock — the browser calls the API directly — so it needs no
# VPC connector and no instance role, just the ECR-pull access role.

resource "aws_ecr_repository" "web" {
  name                 = "${var.app_name}-web"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "web" {
  repository = aws_ecr_repository.web.name

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
  service_name = "${var.app_name}-web"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }
    auto_deployments_enabled = true

    image_repository {
      image_identifier      = "${aws_ecr_repository.web.repository_url}:${var.image_tag}"
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

output "web_url" {
  description = "Public HTTPS URL of the Next.js web client"
  value       = "https://${aws_apprunner_service.web.service_url}"
}

output "web_ecr_repository_url" {
  description = "ECR repository for the web image"
  value       = aws_ecr_repository.web.repository_url
}
