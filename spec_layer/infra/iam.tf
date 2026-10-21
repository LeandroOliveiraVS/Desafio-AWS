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
    sid     = "LerScripts"
    actions = ["s3:GetObject"]
    resources = [
      "${data.aws_s3_bucket.artefatos.arn}/${aws_s3_object.spec_job.key}",
      "${data.aws_s3_bucket.artefatos.arn}/${aws_s3_object.spec_libs.key}",
    ]
  }

  # Arquivos das tabelas Iceberg da Silver; as views podem ler qualquer tabela do database.
  statement {
    sid       = "LerOrigem"
    actions   = ["s3:ListBucket", "s3:GetObject"]
    resources = [data.aws_s3_bucket.origem.arn, "${data.aws_s3_bucket.origem.arn}/${var.prefixo_origem}/silver.db/*"]
  }

  # Leitura das tabelas Silver pelo catálogo Iceberg
  statement {
    sid = "LerCatalogSilver"
    actions = [
      "glue:GetDatabase",
      "glue:GetTable",
      "glue:GetTables",
    ]
    resources = [
      "arn:aws:glue:${var.regiao}:${local.conta_id}:catalog",
      "arn:aws:glue:${var.regiao}:${local.conta_id}:database/silver",
      "arn:aws:glue:${var.regiao}:${local.conta_id}:table/silver/*",
    ]
  }

  statement {
    sid = "GravarGold"
    actions = [
      "s3:ListBucket",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [data.aws_s3_bucket.destino.arn, "${data.aws_s3_bucket.destino.arn}/${var.prefixo_destino}/*"]
  }

  # Database `gold` e tabelas das business views criadas pelo spec_job.py
  statement {
    sid = "GravarCatalogGold"
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
      "arn:aws:glue:${var.regiao}:${local.conta_id}:database/gold",
      "arn:aws:glue:${var.regiao}:${local.conta_id}:table/gold/*",
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
