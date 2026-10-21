"""
Job Glue da camada Bronze: lê os Parquet da origem e grava as tabelas Iceberg.

As regras ficam em `raw_transformacoes.py`, que precisa ser enviado ao job
via `--extra-py-files`.
"""
import sys
import logging

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

from raw_transformacoes import Bronze

## @params: [JOB_NAME]
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'bucket_origem', 'bucket_bronze'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args['JOB_NAME'], args)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print('##############################')
print('----- GLUE JOB INITIATED -----')
print('##############################')

bronze = Bronze(spark)

caminho_origem = bronze.montar_caminho_origem(args["bucket_origem"])

logger.info("Lendo dados da origem: %s", caminho_origem)

dy_origem = glueContext.create_dynamic_frame.from_options(
    connection_type="s3",
    connection_options={
        "paths": [caminho_origem],
        "recurse": True,
    },
    format="parquet",
    transformation_ctx="dy_origem",
)

df_origem = dy_origem.toDF()
print(f"Schema lido da origem: {df_origem.schema.simpleString()}")

df_bronze = bronze.aplicar_contrato(df_origem)
print(f"Schema após aplicar o contrato: {df_bronze.schema.simpleString()}")

# Cria o banco de dados no Glue Data Catalog, caso ainda não exista.
bronze.criar_database("bronze")

print('#### Tabela Bronze Primaria Iceberg V3')
bronze.gravar_tabela_iceberg(df_bronze, "glue_catalog.bronze.transacoes", "3")

# Versão V2 para leitura pelo Athena, que não suporta Iceberg V3.
print('#### Tabela Bronze Secundaria Iceberg V2')
bronze.gravar_tabela_iceberg(df_bronze, "glue_catalog.bronze.transacoes_alt", "2")

print('##############################')
print('------- GLUE JOB DONE -------')
print('##############################')

job.commit()
