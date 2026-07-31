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

        runtime_environment_variables = merge(
          {
            PORT                     = "8080"
            ENVIRONMENT              = var.app_environment
            ALLOW_DEV_AUTH_HEADERS   = var.allow_dev_auth_headers
            GOOGLE_CLIENT_ID         = var.google_client_id
            CORS_ORIGINS             = var.cors_origins
            RATE_LIMIT_CHAT_PER_MIN  = tostring(var.rate_limit_chat_per_min)
            RATE_LIMIT_STORE_PER_MIN = tostring(var.rate_limit_store_per_min)
          },
          # App Runner drops blank env vars; omit instead of forcing perpetual drift.
          trimspace(var.super_admin_email) != "" ? {
            SUPER_ADMIN_EMAIL = var.super_admin_email
          } : {},
          local.llm_env,
          local.langfuse_enabled ? {
            LANGFUSE_ENABLED             = "true"
            LANGFUSE_BASE_URL            = var.langfuse_base_url
            LANGFUSE_TRACING_ENVIRONMENT = var.langfuse_tracing_environment
          } : {},
        )

        runtime_environment_secrets = merge(
          {
            POSTGRES_URL = aws_secretsmanager_secret.postgres_url.arn
          },
          local.use_home_gpu ? {
            OPENAI_API_KEY = aws_secretsmanager_secret.home_gpu_api_key[0].arn
            EMBED_API_KEY  = aws_secretsmanager_secret.home_gpu_api_key[0].arn
          } : {},
          local.langfuse_enabled ? {
            LANGFUSE_PUBLIC_KEY = aws_secretsmanager_secret.langfuse_public_key[0].arn
            LANGFUSE_SECRET_KEY = aws_secretsmanager_secret.langfuse_secret_key[0].arn
          } : {},
        )
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
    # Without these explicit deps, a targeted apply of just this service can
    # create the roles but skip their policies — App Runner then fails to pull
    # the image ("Invalid Access Role") or to read secrets / call Bedrock.
    aws_iam_role_policy_attachment.apprunner_ecr,
    aws_iam_role_policy.apprunner_secrets,
    aws_iam_role_policy.apprunner_bedrock,
    aws_secretsmanager_secret_version.postgres_url,
    aws_db_instance.main,
  ]
}
