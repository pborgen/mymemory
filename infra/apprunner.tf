resource "aws_apprunner_service" "main" {
  service_name = var.app_name

  source_configuration {
    # Pull from our private ECR repo.
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }

    # Redeploy automatically when a new image is pushed to the tag.
    auto_deployments_enabled = true

    image_repository {
      image_identifier      = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "8080"

        runtime_environment_variables = {
          PORT                   = "8080"
          ALLOW_DEV_AUTH_HEADERS = var.allow_dev_auth_headers
          GOOGLE_CLIENT_ID       = var.google_client_id
          # Region + models for the Bedrock-hosted generation + embeddings.
          AWS_REGION     = var.aws_region
          RAG_MODEL_ID   = var.rag_model_id
          EMBED_MODEL_ID = var.embed_model_id
        }

        runtime_environment_secrets = {
          POSTGRES_URL = aws_secretsmanager_secret.postgres_url.arn
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.apprunner_cpu
    memory            = var.apprunner_memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  # Egress through the VPC connector so the service can reach private RDS.
  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.main.arn
    }
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/api/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  depends_on = [
    aws_iam_role_policy.apprunner_secrets,
    aws_db_instance.main,
  ]
}
