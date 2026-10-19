# Layer com as dependências (gerada por scripts/build_layer.sh)
resource "aws_s3_object" "layer" {
  bucket      = data.aws_s3_bucket.destino.id
  key         = "${var.prefixo_artefatos}/layers/data_generator/layer-${filemd5(local.layer_zip)}.zip"
  source      = local.layer_zip
  source_hash = filemd5(local.layer_zip)
}

resource "aws_lambda_layer_version" "dependencias" {
  layer_name          = "${local.nome_base}-dependencias"
  s3_bucket           = aws_s3_object.layer.bucket
  s3_key              = aws_s3_object.layer.key
  source_code_hash    = filebase64sha256(local.layer_zip)
  compatible_runtimes = ["python3.12"]
}

# Pacote com o código da aplicação e os CSVs de contas/contratos
data "archive_file" "app" {
  type        = "zip"
  output_path = "${path.module}/build/app.zip"

  dynamic "source" {
    for_each = local.app_arquivos

    content {
      content  = file("${local.app_dir}/${source.value}")
      filename = "generate_layer/app/${source.value}"
    }
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.nome_base}-data-generator"
  retention_in_days = var.retencao_logs_dias
}

resource "aws_lambda_function" "data_generator" {
  function_name    = "${local.nome_base}-data-generator"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  handler          = "generate_layer.app.lambda_function.lambda_handler"
  filename         = data.archive_file.app.output_path
  source_code_hash = data.archive_file.app.output_base64sha256
  layers           = [aws_lambda_layer_version.dependencias.arn]
  memory_size      = var.lambda_memoria_mb
  timeout          = var.lambda_timeout_s

  environment {
    variables = {
      BUCKET_DESTINO  = data.aws_s3_bucket.destino.id
      PREFIXO_DESTINO = var.prefixo_destino
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.lambda.name
  }

  depends_on = [aws_iam_role_policy.lambda]
}
