# Role de execução do job Glue
data "aws_iam_policy_document" "glue_job_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.conta_id]
    }
  }
}

resource "aws_iam_role" "glue_job" {
  name               = "${local.nome_base}-glue-job"
  assume_role_policy = data.aws_iam_policy_document.glue_job_assume.json
}

data "aws_iam_policy_document" "glue_job" {
  statement {
    sid       = "LerScriptJobGlueSilver"
    actions   = ["s3:GetObject"]
    resources = ["${data.aws_s3_bucket.artefatos.arn}/${aws_s3_object.sot_job.key}"]
  }

  statement {
    sid       = "LerScriptGlueSilver"
    actions   = ["s3:GetObject"]
    resources = ["${data.aws_s3_bucket.artefatos.arn}/${aws_s3_object.sot_transform.key}"]
  }

  statement {
    sid       = "LerOrigem"
    actions   = ["s3:ListBucket", "s3:GetObject"]
    resources = [data.aws_s3_bucket.origem.arn, "${data.aws_s3_bucket.origem.arn}/bronze.db/transacoes/*"]
  }

  # Leitura da tabela Bronze pelo catálogo Iceberg
  statement {
    sid = "LerCatalogBronze"
    actions = [
      "glue:GetDatabase",
      "glue:GetTable",
      "glue:GetTables",
    ]
    resources = [
      "arn:aws:glue:${var.regiao}:${local.conta_id}:catalog",
      "arn:aws:glue:${var.regiao}:${local.conta_id}:database/bronze",
      "arn:aws:glue:${var.regiao}:${local.conta_id}:table/bronze/*",
    ]
  }

  statement {
    sid = "GravarSilver"
    actions = [
      "s3:ListBucket",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [data.aws_s3_bucket.destino.arn, "${data.aws_s3_bucket.destino.arn}/*"]
  }

  # Database `silver` e tabelas criadas pelo sot_job.py
  statement {
    sid = "GravarCatalogSilver"
    actions = [
      "glue:GetDatabase",
      "glue:CreateDatabase",
      "glue:GetTable",
      "glue:GetTables",
      "glue:CreateTable",
      "glue:UpdateTable",
    ]
    resources = [
      "arn:aws:glue:${var.regiao}:${local.conta_id}:catalog",
      "arn:aws:glue:${var.regiao}:${local.conta_id}:database/silver",
      "arn:aws:glue:${var.regiao}:${local.conta_id}:table/silver/*",
    ]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.regiao}:${local.conta_id}:log-group:/aws-glue/*"]
  }

  statement {
    sid       = "Metricas"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["Glue"]
    }
  }
}

resource "aws_iam_role_policy" "glue_job" {
  name   = "${local.nome_base}-glue-job"
  role   = aws_iam_role.glue_job.id
  policy = data.aws_iam_policy_document.glue_job.json
}