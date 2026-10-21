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
  description = "Bucket S3 já existente da camada Silver (origem das business views)."
  type        = string
  default     = "desafio-aws-silver"
}

variable "bucket_destino" {
  description = "Bucket S3 já existente onde as business views serão armazenadas (destino da camada Gold)."
  type        = string
  default     = "desafio-aws-gold"
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
