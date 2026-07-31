# ── LLM backend: locals + NAT / secrets ──────────
# Profile selected by var.llm_backend (see variables.tf).
#   bedrock  → PrivateLink for Bedrock; NAT only if Google auth needs HTTPS out
#   home_gpu → NAT + Cloudflare Tunnel URLs + shared bearer secret
#
# App Runner uses egress_type=VPC (private RDS). Without NAT, the service cannot
# reach the public internet — Google ID-token verify fetches certs from
# googleapis.com and hangs (504). Enable NAT whenever Google auth is configured.

locals {
  use_home_gpu = var.llm_backend == "home_gpu"
  # NAT for home_gpu tunnels and/or Google token verification.
  need_nat = local.use_home_gpu || trimspace(var.google_client_id) != ""

  llm_env_bedrock = {
    GEN_PROVIDER   = "bedrock"
    EMBED_PROVIDER = "bedrock"
    AWS_REGION     = var.aws_region
    RAG_MODEL_ID   = var.rag_model_id
    EMBED_MODEL_ID = var.embed_model_id
  }

  llm_env_home_gpu = {
    GEN_PROVIDER      = "openai"
    OPENAI_BASE_URL   = var.home_gpu_openai_base_url
    OPENAI_CHAT_MODEL = var.home_gpu_chat_model
    EMBED_PROVIDER    = "ollama"
    EMBED_BASE_URL    = var.home_gpu_embed_base_url
    EMBED_MODEL_ID    = var.home_gpu_embed_model
    EMBED_DIM         = tostring(var.home_gpu_embed_dim)
    AWS_REGION        = var.aws_region
  }

  llm_env = local.use_home_gpu ? local.llm_env_home_gpu : local.llm_env_bedrock

  # Subnets used by the App Runner VPC connector (+ Bedrock VPCE when present).
  apprunner_subnet_ids = local.need_nat ? aws_subnet.private[*].id : data.aws_subnets.apprunner.ids
}

# ── NAT path for public HTTPS egress (Google certs / Cloudflare Tunnel) ──
# Default-VPC public subnets have no NAT; connector ENIs get private IPs only.

data "aws_subnet" "apprunner_public" {
  for_each = toset(data.aws_subnets.apprunner.ids)
  id       = each.value
}

locals {
  # Stable unique AZ list from existing App Runner-capable public subnets (cap at 2).
  private_azs = slice(
    sort(distinct([for s in data.aws_subnet.apprunner_public : s.availability_zone])),
    0,
    min(2, length(distinct([for s in data.aws_subnet.apprunner_public : s.availability_zone]))),
  )
  # Public subnet to host the NAT GW (first by AZ name).
  nat_public_subnet_id = [
    for az in local.private_azs : [
      for id, s in data.aws_subnet.apprunner_public : id if s.availability_zone == az
    ][0]
  ][0]
}

resource "aws_eip" "nat" {
  count  = local.need_nat ? 1 : 0
  domain = "vpc"
  tags   = { Name = "${var.app_name}-nat" }
}

resource "aws_nat_gateway" "main" {
  count         = local.need_nat ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = local.nat_public_subnet_id
  tags          = { Name = "${var.app_name}-nat" }
}

resource "aws_subnet" "private" {
  count             = local.need_nat ? length(local.private_azs) : 0
  vpc_id            = data.aws_vpc.default.id
  availability_zone = local.private_azs[count.index]
  # High octet to avoid colliding with default VPC /20s (typically 172.31.0–48).
  cidr_block              = cidrsubnet(data.aws_vpc.default.cidr_block, 8, 200 + count.index)
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.app_name}-private-${count.index}" }
}

resource "aws_route_table" "private" {
  count  = local.need_nat ? 1 : 0
  vpc_id = data.aws_vpc.default.id
  tags   = { Name = "${var.app_name}-private" }

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[0].id
  }
}

resource "aws_route_table_association" "private" {
  count          = local.need_nat ? length(aws_subnet.private) : 0
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[0].id
}

# Shared bearer for Caddy on the GPU box (OPENAI_API_KEY + EMBED_API_KEY).
resource "random_password" "home_gpu_api_key" {
  count   = local.use_home_gpu && var.home_gpu_api_key == "" ? 1 : 0
  length  = 48
  special = false
}

locals {
  home_gpu_api_key_effective = local.use_home_gpu ? (
    var.home_gpu_api_key != "" ? var.home_gpu_api_key : random_password.home_gpu_api_key[0].result
  ) : ""
}

resource "aws_secretsmanager_secret" "home_gpu_api_key" {
  count       = local.use_home_gpu ? 1 : 0
  name_prefix = "${var.app_name}/home-gpu-api-key-"
  description = "Bearer token App Runner sends to the home-GPU Cloudflare Tunnel"
}

resource "aws_secretsmanager_secret_version" "home_gpu_api_key" {
  count         = local.use_home_gpu ? 1 : 0
  secret_id     = aws_secretsmanager_secret.home_gpu_api_key[0].id
  secret_string = local.home_gpu_api_key_effective
}

check "home_gpu_urls" {
  assert {
    condition = !local.use_home_gpu || (
      var.home_gpu_openai_base_url != "" && var.home_gpu_embed_base_url != ""
    )
    error_message = "llm_backend=home_gpu requires home_gpu_openai_base_url and home_gpu_embed_base_url (Cloudflare Tunnel HTTPS URLs)."
  }
}
