# Fila e DLQ

resource "aws_sqs_queue" "contratos_dlq" {
  name                      = "${var.projeto}-contratos-dlq"
  message_retention_seconds = 1209600 # 14 dias para investigar falhas
}

resource "aws_sqs_queue" "contratos" {
  name                       = "${var.projeto}-contratos"
  visibility_timeout_seconds = 300
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.contratos_dlq.arn
    maxReceiveCount     = 3
  })
}

# Permissão para o S3 publicar na fila e notificação do bucket

data "aws_iam_policy_document" "fila_contratos" {
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.contratos.arn]
    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [data.aws_s3_bucket.origem.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.conta_id]
    }
  }
}

resource "aws_sqs_queue_policy" "contratos" {
  queue_url = aws_sqs_queue.contratos.id
  policy    = data.aws_iam_policy_document.fila_contratos.json
}

resource "aws_s3_bucket_notification" "contratos" {
  bucket = data.aws_s3_bucket.origem.id

  queue {
    queue_arn     = aws_sqs_queue.contratos.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "contratos/"
    filter_suffix = ".parquet"
  }

  # O S3 valida a permissão da fila ao salvar a notificação.
  depends_on = [aws_sqs_queue_policy.contratos]
}

# Pipe: SQS -> Step Functions

resource "aws_pipes_pipe" "contratos_sfn" {
  name     = "${var.projeto}-contratos-sfn"
  role_arn = aws_iam_role.pipe.arn
  source   = aws_sqs_queue.contratos.arn
  target   = aws_sfn_state_machine.sfn.arn

  source_parameters {
    sqs_queue_parameters {
      batch_size                         = 10
      maximum_batching_window_in_seconds = 300 # junta arquivos que chegam juntos
    }
    # Só eventos de arquivo criado. Descarta o "s3:TestEvent" que o S3 envia
    # ao salvar a notificação, que dispararia uma execução à toa.
    filter_criteria {
      filter {
        pattern = jsonencode({
          body = { Records = { eventName = [{ prefix = "ObjectCreated:" }] } }
        })
      }
    }
  }

  target_parameters {
    step_function_state_machine_parameters {
      invocation_type = "FIRE_AND_FORGET" # obrigatório para workflows Standard
    }
  }
}