provider "aws" {
  region = var.regiao

  default_tags {
    tags = {
      Projeto = var.projeto
      Camada = "geral"
      Gerido  = "terraform"
    }
  }
}

data "aws_caller_identity" "atual" {}

# Bucket origem dos dados
data "aws_s3_bucket" "origem" {
  bucket = var.bucket_origem
}
# Bucket destino dos dados processados
data "aws_s3_bucket" "destino" {
  bucket = var.datalake
}
# Bucket para armazenar os scripts, querys e arquivos temporários
data "aws_s3_bucket" "artefatos" {
  bucket = var.bucket_artefatos
}

locals {
  conta_id  = data.aws_caller_identity.atual.account_id

  #app_dir = "${path.module}/../app"
}