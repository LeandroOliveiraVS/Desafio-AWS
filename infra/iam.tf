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
  name               = "${var.projeto}-step-function"
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
  name   = "${var.projeto}-step-function"
  role   = aws_iam_role.step_function.id
  policy = data.aws_iam_policy_document.step_function.json
}