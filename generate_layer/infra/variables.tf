variable "regiao" {
  description = "Região AWS onde os recursos serão criados."
  type        = string
  default     = "us-east-1"
}

variable "projeto" {
  description = "Prefixo usado no nome dos recursos."
  type        = string
  default     = "aws-desafio"
}

variable "bucket_destino" {
  description = "Bucket S3 já existente onde os Parquet são gravados (origem da camada Bronze)."
  type        = string
  default     = "desafio-aws-contratos"
}

variable "prefixo_destino" {
  description = "Prefixo no bucket de destino onde os Parquet são gravados."
  type        = string
  default     = "contratos"
}

variable "prefixo_artefatos" {
  description = "Prefixo no bucket de destino onde o zip da Lambda Layer é publicado."
  type        = string
  default     = "artefatos"
}

variable "quantidade_registros" {
  description = "Quantidade de transações geradas a cada execução agendada."
  type        = number
  default     = 1000
}

variable "taxa_erros" {
  description = "Fração (0 a 1) dos registros gerados com erro proposital (chave nula ou duplicata) a cada execução agendada."
  type        = number
  default     = 0.02

  validation {
    condition     = var.taxa_erros >= 0 && var.taxa_erros <= 1
    error_message = "A taxa_erros deve estar entre 0 e 1."
  }
}

variable "agendamento" {
  description = "Expressão do EventBridge Scheduler (rate ou cron) que dispara a Lambda."
  type        = string
  default     = "cron(0 6,14,20 ? * MON-FRI *)"
}

variable "fuso_horario" {
  description = "Fuso horário em que a expressão de agendamento é avaliada."
  type        = string
  default     = "America/Sao_Paulo"
}

variable "agendamento_ativo" {
  description = "Liga ou desliga o gatilho de tempo sem destruir o agendamento."
  type        = bool
  default     = true
}

variable "lambda_memoria_mb" {
  description = "Memória da Lambda em MB."
  type        = number
  default     = 512
}

variable "lambda_timeout_s" {
  description = "Timeout da Lambda em segundos."
  type        = number
  default     = 120
}

variable "retencao_logs_dias" {
  description = "Dias de retenção dos logs no CloudWatch."
  type        = number
  default     = 14
}
