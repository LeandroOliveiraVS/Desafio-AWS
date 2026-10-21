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
  description = "Bucket S3 do data lake onde está a camada Bronze (origem da Silver)."
  type        = string
  default     = "desafio-aws-datalake"
}

variable "prefixo_origem" {
  description = "Prefixo da camada Bronze no data lake."
  type        = string
  default     = "bronze"
}

variable "bucket_destino" {
  description = "Bucket S3 do data lake (criado em infra/datalake.tf)."
  type        = string
  default     = "desafio-aws-datalake"
}

variable "prefixo_destino" {
  description = "Prefixo da camada Silver no data lake (warehouse das tabelas Iceberg)."
  type        = string
  default     = "silver"
}

variable "bucket_artefatos" {
  description = "Bucket S3 já existente onde os scripts são armazenados."
  type        = string
  default     = "desafio-aws-artefatos"
}