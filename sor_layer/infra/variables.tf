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

variable "bucket_destino" {
  description = "Bucket S3 já existente onde os dados processados serão armazenados (destino da camada Prata)."
  type        = string
  default     = "desafio-aws-bronze"
}

variable "bucket_artefatos" {
  description = "Bucket S3 já existente onde os scripts são armazenados."
  type        = string
  default     = "desafio-aws-artefatos"
}