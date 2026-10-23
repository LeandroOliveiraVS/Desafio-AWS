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

variable "bucket_origem" {
  description = "Bucket S3 já existente onde os Parquet são gravados (origem da camada Bronze)."
  type        = string
  default     = "desafio-aws-contratos"
}

variable "datalake" {
  description = "Nome do bucket S3 do data lake, criado por este projeto (datalake.tf)."
  type        = string
  default     = "desafio-aws-datalake"
}

variable "bucket_artefatos" {
  description = "Bucket S3 já existente onde os scripts são armazenados."
  type        = string
  default     = "desafio-aws-artefatos"
}

variable "business_views" {
  description = "Business views da camada Gold executadas pela state machine (nomes dos arquivos em spec_layer/app/src/business_views/, sem .py)."
  type        = list(string)
  default     = ["saldo_conta_por_contrato"]

  validation {
    condition     = length(var.business_views) > 0
    error_message = "Informe ao menos uma business view."
  }
}
