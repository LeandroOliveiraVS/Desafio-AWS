resource "aws_s3_object" "sot_job" {
  bucket = data.aws_s3_bucket.artefatos.id
  key    = "scripts/sot_job.py"
  source = "${local.app_dir}/src/sot_job.py"
  etag   = filemd5("${local.app_dir}/src/sot_job.py")
}

resource "aws_s3_object" "sot_transform" {
  bucket = data.aws_s3_bucket.artefatos.id
  key    = "scripts/sot_transform.py"
  source = "${local.app_dir}/src/sot_transform.py"
  etag   = filemd5("${local.app_dir}/src/sot_transform.py")
}

resource "aws_glue_job" "etl_job" {
  name        = "${local.nome_base}-etl-job"
  description = "Lê os Icebergs da origem e grava as tabelas Iceberg da camada Silver."
  role_arn    = aws_iam_role.glue_job.arn
  glue_version      = "6.0"
  max_retries       = 0 # as retentativas ficam com o Step Functions
  timeout           = 10
  number_of_workers = 2
  worker_type       = "G.1X"
  execution_class   = "STANDARD"

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_object.sot_job.bucket}/${aws_s3_object.sot_job.key}"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--continuous-log-logGroup"          = "/aws-glue/jobs"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-continuous-log-filter"     = "true"
    "--enable-metrics"                   = ""
    "--enable-auto-scaling"              = "false"

    # Parâmetros lidos pelo raw_processor.py
    "--bucket_origem" = data.aws_s3_bucket.origem.bucket
    "--bucket_silver" = data.aws_s3_bucket.destino.bucket

    "--extra-py-files" = "s3://${aws_s3_object.sot_transform.bucket}/${aws_s3_object.sot_transform.key}"
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

  execution_property {
    max_concurrent_runs = 1
  }
}