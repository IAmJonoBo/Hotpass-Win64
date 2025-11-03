locals {
  default_subjects = [
    "repo:${var.github_repository}:ref:refs/heads/main",
    "repo:${var.github_repository}:environment:arc-runners",
    "repo:${var.github_repository}:pull_request",
  ]
  allowed_subjects    = distinct(concat(locals.default_subjects, var.oidc_subjects))
  artifact_resources  = var.s3_artifact_bucket != "" ? [var.s3_artifact_bucket, "${var.s3_artifact_bucket}/*"] : ["*"]
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]  # pragma: allowlist secret - public GitHub OIDC thumbprint
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = locals.allowed_subjects
    }
  }
}

resource "aws_iam_role" "arc_runner" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.github_assume.json

  tags = {
    "app.kubernetes.io/component" = "arc-runners"
    "app.kubernetes.io/name"      = "hotpass"
  }
}

data "aws_iam_policy_document" "runner_permissions" {
  statement {
    sid     = "ContainerRegistryAccess"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "CloudWatchLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "ArtifactStorage"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = locals.artifact_resources
  }
}

resource "aws_iam_role_policy" "arc_runner" {
  name   = "arc-runner-permissions"
  role   = aws_iam_role.arc_runner.id
  policy = data.aws_iam_policy_document.runner_permissions.json
}
