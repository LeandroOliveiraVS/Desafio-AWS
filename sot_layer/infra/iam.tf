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
}