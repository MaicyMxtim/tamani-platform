# Identity for External Secrets Operator: read-only access to the
# /tamani/* path in SSM Parameter Store, nothing else. The secret VALUES
# are put into SSM out-of-band (never through Terraform state).

resource "aws_iam_user" "eso" {
  name = "tamani-eso-reader"
}

resource "aws_iam_user_policy" "eso_ssm_read" {
  name = "ssm-read-tamani"
  user = aws_iam_user.eso.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
      Resource = "arn:aws:ssm:${var.region}:*:parameter/tamani/*"
    }]
  })
}

resource "aws_iam_access_key" "eso" {
  user = aws_iam_user.eso.name
}

output "eso_access_key_id" {
  value     = aws_iam_access_key.eso.id
  sensitive = true
}

output "eso_secret_access_key" {
  value     = aws_iam_access_key.eso.secret
  sensitive = true
}
