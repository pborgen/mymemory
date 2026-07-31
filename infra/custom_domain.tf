# Custom domains for the public API (App Runner).
# Web UI lives on Vercel — see infra/DOMAINS.md (GoDaddy DNS).
#
# Recommended:
#   web  → memory.informedbydata.com          (Vercel)
#   api  → api.memory.informedbydata.com      (this file)

variable "api_custom_domain" {
  description = "FQDN for the API (e.g. api.memory.informedbydata.com). Blank skips association."
  type        = string
  default     = ""
}

variable "deploy_web_on_apprunner" {
  description = "Keep the App Runner Next.js service. Set false when the web app is on Vercel."
  type        = bool
  default     = false
}

resource "aws_apprunner_custom_domain_association" "api" {
  count                = var.api_custom_domain != "" ? 1 : 0
  domain_name          = var.api_custom_domain
  service_arn          = aws_apprunner_service.main.arn
  enable_www_subdomain = false
}

output "api_custom_domain" {
  description = "Custom API hostname (empty if unused)"
  value       = var.api_custom_domain
}

output "api_custom_domain_dns_target" {
  description = "CNAME target for the API hostname (point GoDaddy here)"
  value       = try(aws_apprunner_custom_domain_association.api[0].dns_target, "")
}

output "api_custom_domain_certificate_validation" {
  description = "ACM validation CNAMEs to add at GoDaddy (name → value)"
  value = try([
    for r in aws_apprunner_custom_domain_association.api[0].certificate_validation_records : {
      name  = r.name
      type  = r.type
      value = r.value
    }
  ], [])
}
