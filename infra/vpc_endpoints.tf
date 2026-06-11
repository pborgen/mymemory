# The App Runner service egresses ALL traffic through the VPC connector
# (egress_type = "VPC", so it can reach private RDS). The default-VPC subnets
# have no NAT gateway, so the instance has no route to the public internet.
#
# The memory engine calls Bedrock at runtime for BOTH embeddings (Titan) and
# answer generation (Claude). Both go to the bedrock-runtime API, so without a
# path to it they would time out. Rather than add a NAT gateway (and expose the
# service to the whole internet), we add a PrivateLink interface endpoint for the
# Bedrock runtime API. Secrets Manager is NOT needed here: App Runner injects
# runtime_environment_secrets via its managed infrastructure, not the connector.

# Security group for the interface endpoint: allow HTTPS from the App Runner connector.
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.app_name}-vpce-"
  description = "HTTPS from App Runner connector to interface VPC endpoints"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "HTTPS from App Runner connector"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.apprunner.id]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Bedrock runtime (InvokeModel) — used by both Titan embeddings and Claude.
resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = data.aws_vpc.default.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = data.aws_subnets.apprunner.ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}
