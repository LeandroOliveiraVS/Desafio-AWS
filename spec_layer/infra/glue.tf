resource "aws_s3_object" "spec_job" {
  bucket = data.aws_s3_bucket.artefatos.id
  key    = "scripts/spec_job.py"
  source = "${local.app_dir}/src/spec_job.py"
  etag   = filemd5("${local.app_dir}/src/spec_job.py")
}

# spec_transform.py + pacote business_views, enviados via --extra-py-files.
# Uma business view nova entra no zip automaticamente.
data "archive_file" "spec_libs" {
  type        = "zip"
  source_dir  = "${local.app_dir}/src"
  output_path = "${path.module}/build/spec_libs.zip"
  excludes    = ["spec_job.py", "**/__pycache__/**"]
}

resource "aws_s3_object" "spec_libs" {
  bucket = data.aws_s3_bucket.artefatos.id
  key    = "scripts/spec_libs.zip"
  source = data.archive_file.spec_libs.output_path
  etag   = data.archive_file.spec_libs.output_md5
}

resource "aws_glue_job" "etl_job" {
  name              = "${local.nome_base}-etl-job"
  description       = "Lê as tabelas da camada Silver e grava as business views da camada Gold."
  role_arn          = aws_iam_role.glue_job.arn
  glue_version      = "6.0"
  max_retries       = 0 # as retentativas ficam com o Step Functions
  timeout           = 10
  number_of_workers = 2
  worker_type       = "G.1X"
  execution_class   = "STANDARD"

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_object.spec_job.bucket}/${aws_s3_object.spec_job.key}"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--continuous-log-logGroup"          = "/aws-glue/jobs"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-continuous-log-filter"     = "true"
    "--enable-metrics"                   = ""
    "--enable-auto-scaling"              = "false"

    # Parâmetros lidos pelo spec_job.py. O `--business_view` (nome do arquivo
    # em business_views/) é informado em cada execução.
    "--tabela_origem"    = "glue_catalog.silver.transacoes"
    "--database_destino" = "gold"

    "--extra-py-files" = "s3://${aws_s3_object.spec_libs.bucket}/${aws_s3_object.spec_libs.key}"
  }

  # Configuração do Iceberg; não pode ser sobrescrita na execução.
  non_overridable_arguments = {
    "--datalake-formats" = "iceberg"
    "--conf" = join(" --conf ", [
      "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
      "spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog",
      "spark.sql.catalog.glue_catalog.warehouse=s3://${data.aws_s3_bucket.destino.bucket}/",
      "spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog",
      "spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO",
    ])
  }

  # Cada business view é uma execução do job; views diferentes rodam em paralelo.
  execution_property {
    max_concurrent_runs = var.max_execucoes_simultaneas
  }
}
