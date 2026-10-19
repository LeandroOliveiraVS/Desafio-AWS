resource "aws_s3_object" "glue_etl_script" {
  bucket = data.aws_s3_bucket.artefatos.id
  key    = "scripts/raw_processor.py"
  source = "${local.app_dir}/src/raw_processor.py"
}

resource "aws_glue_job" "etl_job" {
    name = "${local.nome_base}-etl-job"
    description = "ETL job to process raw data and store it in S3"
    role_arn = aws_iam_role.glue_job.arn
    glue_version      = "5.0"
    max_retries       = 0
    timeout           = 2880
    number_of_workers = 2
    worker_type       = "G.1X"
    execution_class   = "STANDARD"

    command {
        name            = "glueetl"
        script_location = "s3://${data.aws_s3_bucket.artefatos.bucket}/scripts/raw_processor.py"
        python_version  = "3"
    }

    default_arguments = {
    "--job-language"                     = "python"
    "--continuous-log-logGroup"          = "/aws-glue/jobs"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-continuous-log-filter"     = "true"
    "--enable-metrics"                   = ""
    "--enable-auto-scaling"              = "true"
  }

  execution_property {
    max_concurrent_runs = 1
  }
}