terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Local state until the S3 + DynamoDB backend is bootstrapped (Phase 0
  # completion step; requires the bucket to exist first).
}

provider "aws" {
  region = var.region
}
