import sys
import logging
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import col
from pyspark.sql.types import (
    BooleanType,
    DateType,
    DecimalType,
    StringType,
    TimestampType,
)

# Contrato de dados gerado pela camada generate_layer (LambdaHandler.SCHEMA).
SCHEMA_CONTRATO = {
    "id_transacao": StringType(),
    "id_contrato": StringType(),
    "id_conta": StringType(),
    "cnpj": StringType(),
    "cod_agencia": StringType(),
    "tipo_contrato": StringType(),
    "tipo_lancamento": StringType(),
    "valor_lancamento": DecimalType(18, 2),
    "dt_lancamento": TimestampType(),
    "dt_processamento": DateType(),
    "cod_cosif": StringType(),
    "flag_estorno": BooleanType(),
    "id_lote": StringType(),
}

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

bucket_origem = args["bucket_origem"]
caminho_origem = f"s3://{bucket_origem}/contratos/"

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

logger.info("Leitura do DynamicFrame concluída.")

df_origem = dy_origem.toDF()

print(f"Schema lido da origem: {df_origem.schema.simpleString()}")

# Garante que a Bronze receba sempre as colunas e os tipos do contrato,
# falhando com uma mensagem clara se a origem mudar.
colunas_faltantes = set(SCHEMA_CONTRATO) - set(df_origem.columns)
if colunas_faltantes:
    raise ValueError(
        f"Colunas do contrato ausentes na origem: {sorted(colunas_faltantes)}"
    )

df_origem = df_origem.select(
    [col(nome).cast(tipo).alias(nome) for nome, tipo in SCHEMA_CONTRATO.items()]
)

print(f"Schema após aplicar o contrato: {df_origem.schema.simpleString()}")

# Cria o banco de dados no Glue Data Catalog, caso ainda não exista.
spark.sql("CREATE DATABASE IF NOT EXISTS glue_catalog.bronze")

nome_tabela = "glue_catalog.bronze.transacoes"
nome_tabela_alt = "glue_catalog.bronze.transacoes_alt"

logger.info("Iniciando gravação da tabela Iceberg: %s", nome_tabela)

table_exists = spark.catalog.tableExists(nome_tabela)
table_alt_exists = spark.catalog.tableExists(nome_tabela_alt)

print('#### Tabela Bronze Primaria Iceberg V3')
if not table_exists:
    logger.info(
            "Tabela %s não encontrada. Criando tabela Iceberg "
            "com partição por dt_processamento.",
            nome_tabela,
        )
    (
        df_origem.writeTo(nome_tabela)
        .using("iceberg")
        .tableProperty("format-version", "3")
        .partitionedBy("dt_processamento")
        .create()
    )
else:
    logger.info(
            "Tabela %s já existe. Iniciando substituição das "
            "partições presentes nos dados.",
            nome_tabela,
        )

    df_origem.writeTo(nome_tabela).overwritePartitions()
print('#################################################')
print('#### Tabela Bronze Secundaria Iceberg V2')
if not table_alt_exists:
    logger.info(
            "Tabela %s não encontrada. Criando tabela Iceberg "
            "com partição por dt_processamento.",
            nome_tabela_alt,
        )
    (
        df_origem.writeTo(nome_tabela_alt)
        .using("iceberg")
        .tableProperty("format-version", "2")
        .partitionedBy("dt_processamento")
        .create()
    )
else:
    logger.info(
            "Tabela %s já existe. Iniciando substituição das "
            "partições presentes nos dados.",
            nome_tabela_alt,
        )

    df_origem.writeTo(nome_tabela_alt).overwritePartitions()
print('#################################################')

print('##############################')
print('------- GLUE JOB DONE -------')
print('##############################')

job.commit()