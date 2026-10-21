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
  description = "Bucket S3 do data lake onde está a camada Silver (origem das business views)."
  type        = string
  default     = "desafio-aws-datalake"
}

variable "prefixo_origem" {
  description = "Prefixo da camada Silver no data lake."
  type        = string
  default     = "silver"
}

variable "bucket_destino" {
  description = "Bucket S3 do data lake (criado em infra/datalake.tf)."
  type        = string
  default     = "desafio-aws-datalake"
}

variable "prefixo_destino" {
  description = "Prefixo da camada Gold no data lake (warehouse das tabelas Iceberg)."
  type        = string
  default     = "gold"
}

variable "bucket_artefatos" {
  description = "Bucket S3 já existente onde os scripts são armazenados."
  type        = string
  default     = "desafio-aws-artefatos"
}

variable "max_execucoes_simultaneas" {
  description = "Quantas business views podem rodar ao mesmo tempo no job Gold."
  type        = number
  default     = 3
}
