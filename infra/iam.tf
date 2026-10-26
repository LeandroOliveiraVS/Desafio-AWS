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
    resources = values(local.glue_jobs_arn)
  }
}

resource "aws_iam_role_policy" "step_function" {
  name   = "${var.projeto}-step-function"
  role   = aws_iam_role.step_function.id
  policy = data.aws_iam_policy_document.step_function.json
}

# Permissões para eventos
data "aws_iam_policy_document" "pipe_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["pipes.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.conta_id]
    }
  }
}

resource "aws_iam_role" "pipe" {
  name               = "${var.projeto}-pipe-contratos"
  assume_role_policy = data.aws_iam_policy_document.pipe_assume.json
}

data "aws_iam_policy_document" "pipe" {
  statement {
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.contratos.arn]
  }
  statement {
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.sfn.arn]
  }
}

resource "aws_iam_role_policy" "pipe" {
  name   = "${var.projeto}-pipe-contratos"
  role   = aws_iam_role.pipe.id
  policy = data.aws_iam_policy_document.pipe.json
}
