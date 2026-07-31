# Use the account's default VPC + subnets to keep the footprint small.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# App Runner is not offered in every AZ (in us-east-1, use1-az3 is unsupported).
# The VPC connector must only reference subnets in App Runner-capable AZs, so we
# filter the default subnets down to the supported availability-zone IDs.
variable "apprunner_az_ids" {
  description = "AZ IDs that support App Runner (default: us-east-1 minus use1-az3)"
  type        = list(string)
  default     = ["use1-az1", "use1-az2", "use1-az4", "use1-az5", "use1-az6"]
}

data "aws_subnets" "apprunner" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "availability-zone-id"
    values = var.apprunner_az_ids
  }
  # Exclude our NAT private subnets (map_public_ip_on_launch=false).
  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

locals {
  # Hash changes when connector subnets change → forces a new SG + connector
  # (App Runner forbids two connectors sharing the same security-group set).
  connector_hash = substr(sha1(join(",", local.apprunner_subnet_ids)), 0, 8)
  # CIDR allow-lists so RDS/VPCE stay reachable while SG+connector rotate.
  apprunner_subnet_cidrs = local.need_nat ? aws_subnet.private[*].cidr_block : [
    for id in data.aws_subnets.apprunner.ids : data.aws_subnet.apprunner_public[id].cidr_block
  ]
}

# Security group for the App Runner VPC connector (egress side).
resource "aws_security_group" "apprunner" {
  # Include subnet hash so a parallel connector can use a different SG.
  name_prefix = "${var.app_name}-apr-${local.connector_hash}-"
  description = "App Runner VPC connector egress (${local.connector_hash})"
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "All egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Security group for RDS: App Runner connector subnet CIDRs only.
resource "aws_security_group" "rds" {
  name_prefix = "${var.app_name}-rds-"
  description = "Postgres access from App Runner connector subnets"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Postgres from App Runner connector subnets"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = local.apprunner_subnet_cidrs
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_apprunner_vpc_connector" "main" {
  # Name must change when subnets change so create_before_destroy can mint a
  # new connector while App Runner still references the old one. SG must also
  # change (see apprunner SG name_prefix) — AWS rejects duplicate SG combos.
  vpc_connector_name = "${var.app_name}-conn-${local.connector_hash}"
  subnets            = local.apprunner_subnet_ids
  security_groups    = [aws_security_group.apprunner.id]

  lifecycle {
    create_before_destroy = true
  }
}
