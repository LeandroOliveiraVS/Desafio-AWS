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
    sid       = "LerScript"
    actions   = ["s3:GetObject"]
    resources = ["${data.aws_s3_bucket.artefatos.arn}/${aws_s3_object.glue_etl_script.key}"]
  }

  statement {
    sid       = "LerOrigem"
    actions   = ["s3:ListBucket", "s3:GetObject"]
    resources = [data.aws_s3_bucket.origem.arn, "${data.aws_s3_bucket.origem.arn}/contratos/*"]
  }

  # Warehouse das tabelas Iceberg
  statement {
    sid = "GravarBronze"
    actions = [
      "s3:ListBucket",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [data.aws_s3_bucket.destino.arn, "${data.aws_s3_bucket.destino.arn}/*"]
  }

  # Database `bronze` e tabelas criadas pelo raw_processor.py
  statement {
    sid = "GlueCatalog"
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
      "arn:aws:glue:${var.regiao}:${local.conta_id}:database/bronze",
      "arn:aws:glue:${var.regiao}:${local.conta_id}:table/bronze/*",
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

# Role da state machine do Step Functions que orquestra o job Glue
data "aws_iam_policy_document" "step_function_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.conta_id]
    }
  }
}

resource "aws_iam_role" "step_function" {
  name               = "${local.nome_base}-step-function"
  assume_role_policy = data.aws_iam_policy_document.step_function_assume.json
}

# Permissões exigidas pela integração síncrona glue:startJobRun.sync
data "aws_iam_policy_document" "step_function" {
  statement {
    sid = "ExecutarJobGlue"
    actions = [
      "glue:StartJobRun",
      "glue:GetJobRun",
      "glue:GetJobRuns",
      "glue:BatchStopJobRun",
    ]
    resources = [aws_glue_job.etl_job.arn]
  }
}

resource "aws_iam_role_policy" "step_function" {
  name   = "${local.nome_base}-step-function"
  role   = aws_iam_role.step_function.id
  policy = data.aws_iam_policy_document.step_function.json
}
