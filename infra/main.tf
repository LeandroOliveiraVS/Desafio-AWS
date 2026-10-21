provider "aws" {
  region = var.regiao

  default_tags {
    tags = {
      Projeto = var.projeto
      Camada  = "geral"
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
  conta_id = data.aws_caller_identity.atual.account_id

  # Jobs Glue criados nas pastas de infra de cada camada (nome_base + "-etl-job").
  glue_jobs = {
    for camada in ["sor", "sot", "spec"] :
    camada => "${var.projeto}-${camada}-etl-job"
  }
  glue_jobs_arn = {
    for camada, nome in local.glue_jobs :
    camada => "arn:aws:glue:${var.regiao}:${local.conta_id}:job/${nome}"
  }

  #app_dir = "${path.module}/../app"
}