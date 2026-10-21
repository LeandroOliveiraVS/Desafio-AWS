provider "aws" {
  region = var.regiao

  default_tags {
    tags = {
      Projeto = var.projeto
      Camada  = "spec"
      Gerido  = "terraform"
    }
  }
}

data "aws_caller_identity" "atual" {}

# Bucket origem dos dados (camada Silver)
data "aws_s3_bucket" "origem" {
  bucket = var.bucket_origem
}
# Bucket destino das business views (camada Gold)
data "aws_s3_bucket" "destino" {
  bucket = var.bucket_destino
}
# Bucket para armazenar os scripts, querys e arquivos temporários
data "aws_s3_bucket" "artefatos" {
  bucket = var.bucket_artefatos
}

locals {
  nome_base = "${var.projeto}-spec"
  conta_id  = data.aws_caller_identity.atual.account_id

  app_dir = "${path.module}/../app"
}
