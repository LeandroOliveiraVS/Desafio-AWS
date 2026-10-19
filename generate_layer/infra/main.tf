provider "aws" {
  region = var.regiao

  default_tags {
    tags = {
      Projeto = var.projeto
      Camada  = "generate"
      Gerido  = "terraform"
    }
  }
}

data "aws_caller_identity" "atual" {}

# Bucket já existente; o Terraform apenas o referencia.
data "aws_s3_bucket" "destino" {
  bucket = var.bucket_destino
}

locals {
  nome_base = "${var.projeto}-generate"
  conta_id  = data.aws_caller_identity.atual.account_id

  # Código da aplicação; o caminho dentro do zip preserva o pacote
  # `generate_layer.app...` usado nos imports.
  app_dir = "${path.module}/../app"
  app_arquivos = setunion(
    fileset(local.app_dir, "lambda_function.py"),
    fileset(local.app_dir, "src/data_generator/*.{py,csv}"),
  )

  layer_zip = "${path.module}/build/layer.zip"
}
