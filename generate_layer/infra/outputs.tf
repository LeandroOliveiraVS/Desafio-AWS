output "bucket_destino" {
  description = "Bucket com os Parquet gerados (usado como --bucket_origem na camada Bronze)."
  value       = data.aws_s3_bucket.destino.id
}

output "prefixo_destino" {
  description = "Prefixo dos Parquet no bucket de destino."
  value       = var.prefixo_destino
}

output "lambda_nome" {
  description = "Nome da Lambda geradora de dados."
  value       = aws_lambda_function.data_generator.function_name
}

output "agendamento" {
  description = "Nome do agendamento do EventBridge Scheduler."
  value       = aws_scheduler_schedule.data_generator.name
}
