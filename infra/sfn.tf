locals {
  # Retentativa padrão das etapas: até 2 tentativas adicionais, com 2 horas
  # de intervalo. Esgotadas as tentativas, a execução termina com falha.
  retry_glue = [
    {
      ErrorEquals     = ["States.ALL"]
      IntervalSeconds = 7200
      MaxAttempts     = 2
      BackoffRate     = 1
    }
  ]

  # Guarda só o essencial da execução do Glue no estado de saída. Use apenas
  # campos sempre presentes: um campo ausente faria a etapa falhar depois do
  # job concluído e o Retry rodaria o job de novo.
  resultado_glue = {
    "JobName.$"     = "$.JobName"
    "JobRunId.$"    = "$.Id"
    "JobRunState.$" = "$.JobRunState"
  }
}

# Orquestra as camadas Bronze (sor) e Silver (sot); cada etapa espera o job
# Glue terminar (startJobRun.sync) antes de seguir.
resource "aws_sfn_state_machine" "sfn" {
  name     = "${var.projeto}-state-machine"
  role_arn = aws_iam_role.step_function.arn

  definition = jsonencode({
    Comment = "ETL ${var.projeto}: Bronze (sor) -> Silver (sot)"
    StartAt = "Bronze"
    States = {
      Bronze = {
        Type           = "Task"
        Resource       = "arn:aws:states:::glue:startJobRun.sync"
        Parameters     = { JobName = local.glue_jobs["sor"] }
        ResultSelector = local.resultado_glue
        ResultPath     = "$.bronze"
        Retry          = local.retry_glue
        Next           = "Silver"
      }
      Silver = {
        Type           = "Task"
        Resource       = "arn:aws:states:::glue:startJobRun.sync"
        Parameters     = { JobName = local.glue_jobs["sot"] }
        ResultSelector = local.resultado_glue
        ResultPath     = "$.silver"
        Retry          = local.retry_glue
        End            = true
      }
    }
  })
}
