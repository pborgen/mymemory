# The App Runner service egresses ALL traffic through the VPC connector
# (egress_type = "VPC", so it can reach private RDS).
#
# llm_backend = bedrock (no Google client id):
#   Default-VPC public subnets, Bedrock via PrivateLink, no NAT.
#
# Google auth and/or llm_backend = home_gpu:
#   Connector moves to private subnets + NAT (llm_backend.tf) so the service
#   can HTTPS out (googleapis.com certs / Cloudflare Tunnel). Bedrock VPCE
#   stays on those private subnets when using bedrock.

# Security group for the interface endpoint: allow HTTPS from App Runner subnets.
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.app_name}-vpce-"
  description = "HTTPS from App Runner connector subnets to interface VPC endpoints"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTPS from App Runner connector subnets"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = local.apprunner_subnet_cidrs
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Bedrock runtime (InvokeModel) — used when llm_backend=bedrock.
# One subnet/AZ only: interface endpoints bill ~$7/mo per AZ; one is enough.
resource "aws_vpc_endpoint" "bedrock_runtime" {
  count               = local.use_home_gpu ? 0 : 1
  vpc_id              = data.aws_vpc.default.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [local.apprunner_subnet_ids[0]]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}
