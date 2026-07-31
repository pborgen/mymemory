# Static web frontend — S3 + CloudFront (pennies/month at low traffic).
# Next.js `output: "export"` → sync apps/web/out to this bucket.
#
# Optional custom domain: set web_custom_domain (e.g. memory.informedbydata.com)
# and add the ACM cert in us-east-1 (CloudFront requirement).

variable "web_custom_domain" {
  description = "Optional custom hostname for CloudFront (e.g. memory.informedbydata.com)"
  type        = string
  default     = ""
}

variable "web_acm_certificate_arn" {
  description = "ACM cert ARN in us-east-1 covering web_custom_domain (required if domain set)"
  type        = string
  default     = ""
}

check "web_custom_domain_cert" {
  assert {
    condition     = var.web_custom_domain == "" || var.web_acm_certificate_arn != ""
    error_message = "web_custom_domain requires web_acm_certificate_arn (ACM in us-east-1)."
  }
}

resource "aws_s3_bucket" "web" {
  bucket_prefix = "${var.app_name}-web-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "web" {
  bucket                  = aws_s3_bucket.web.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "web" {
  bucket = aws_s3_bucket.web.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "${var.app_name}-web-oac"
  description                       = "OAC for MyMemory static web"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Map /chat → /chat/index.html (Next trailingSlash export layout).
resource "aws_cloudfront_function" "web_url_rewrite" {
  name    = "${var.app_name}-web-url-rewrite"
  runtime = "cloudfront-js-2.0"
  comment = "Pretty URLs for Next.js static export"
  publish = true
  code    = <<-EOF
    function handler(event) {
      var request = event.request;
      var uri = request.uri;
      if (uri.endsWith('/')) {
        request.uri = uri + 'index.html';
      } else if (!uri.includes('.')) {
        request.uri = uri + '/index.html';
      }
      return request;
    }
  EOF
}

resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.app_name} static web"
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # US/EU/CA only — cheapest
  aliases             = var.web_custom_domain != "" ? [var.web_custom_domain] : []

  origin {
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_id                = "s3-web"
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-web"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = true # prompt editor ?key=
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 300
    max_ttl     = 86400

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.web_url_rewrite.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = var.web_custom_domain == ""
    acm_certificate_arn            = var.web_custom_domain != "" ? var.web_acm_certificate_arn : null
    ssl_support_method             = var.web_custom_domain != "" ? "sni-only" : null
    minimum_protocol_version       = var.web_custom_domain != "" ? "TLSv1.2_2021" : null
  }

  custom_error_response {
    error_code            = 403
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 60
  }

  custom_error_response {
    error_code            = 404
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 60
  }
}

data "aws_iam_policy_document" "web_s3" {
  statement {
    sid       = "AllowCloudFrontRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.web.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.web.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id
  policy = data.aws_iam_policy_document.web_s3.json
}

# Allow GitHub deploy role to sync the static site (optional path in CI).
data "aws_iam_policy_document" "github_web_static" {
  statement {
    sid = "WebStaticSync"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetObject",
    ]
    resources = [
      aws_s3_bucket.web.arn,
      "${aws_s3_bucket.web.arn}/*",
    ]
  }
  statement {
    sid       = "WebInvalidate"
    actions   = ["cloudfront:CreateInvalidation"]
    resources = [aws_cloudfront_distribution.web.arn]
  }
}

resource "aws_iam_role_policy" "github_web_static" {
  name   = "${var.app_name}-github-web-static"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_web_static.json
}

output "web_bucket" {
  description = "S3 bucket for the static Next.js export"
  value       = aws_s3_bucket.web.bucket
}

output "web_cloudfront_domain" {
  description = "CloudFront domain (*.cloudfront.net) — use until custom DNS is set"
  value       = aws_cloudfront_distribution.web.domain_name
}

output "web_cloudfront_distribution_id" {
  description = "CloudFront distribution id (for invalidations)"
  value       = aws_cloudfront_distribution.web.id
}

output "web_url" {
  description = "Public HTTPS URL of the static web app"
  value       = var.web_custom_domain != "" ? "https://${var.web_custom_domain}" : "https://${aws_cloudfront_distribution.web.domain_name}"
}
