resource "aws_s3_object" "glue_etl_script" {
  bucket = data.aws_s3_bucket.artefatos.id
  key    = "scripts/glue_etl_script.py"
  source = "${local.app_dir}/src/raw_processor.py"
}