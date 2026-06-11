resource "random_password" "db" {
  count = var.db_password == "" ? 1 : 0
  # Restrict to URL-safe specials so the value drops cleanly into POSTGRES_URL.
  length           = 24
  special          = true
  override_special = "-_."
}

locals {
  db_password = var.db_password != "" ? var.db_password : random_password.db[0].result
  postgres_url = format(
    "postgresql://%s:%s@%s:%s/%s",
    var.db_username,
    local.db_password,
    aws_db_instance.main.address,
    aws_db_instance.main.port,
    var.db_name,
  )
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.app_name}-db"
  subnet_ids = data.aws_subnets.default.ids
}

# Disable forced SSL: the DB is private (App-Runner-only ingress) and the
# `postgres` client connects without TLS config.
resource "aws_db_parameter_group" "main" {
  name_prefix = "${var.app_name}-pg16-"
  family      = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "0"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# RDS Postgres 16 ships pgvector as a trusted extension; the app runs
# `CREATE EXTENSION IF NOT EXISTS vector` on startup as the master user, which
# has permission. No shared_preload_libraries entry is required for pgvector.
resource "aws_db_instance" "main" {
  identifier     = "${var.app_name}-db"
  engine         = "postgres"
  engine_version = "16"

  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = local.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.main.name
  publicly_accessible    = false

  backup_retention_period    = 7
  skip_final_snapshot        = true
  apply_immediately          = true
  auto_minor_version_upgrade = true
}
