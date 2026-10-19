# Gatilho de tempo que dispara a geração de dados
resource "aws_scheduler_schedule" "data_generator" {
  name                         = "${local.nome_base}-data-generator"
  schedule_expression          = var.agendamento
  schedule_expression_timezone = var.fuso_horario
  state                        = var.agendamento_ativo ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.data_generator.arn
    role_arn = aws_iam_role.scheduler.arn

    # Sem `data_particao`, a Lambda usa a data/hora UTC da execução.
    input = jsonencode({
      quantidade = var.quantidade_registros
    })

    retry_policy {
      maximum_retry_attempts = 2
    }
  }
}
