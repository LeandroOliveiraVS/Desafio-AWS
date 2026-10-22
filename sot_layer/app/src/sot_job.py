import sys
from datetime import datetime, timezone
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

from sot_transform import SotTransform

## @params: [JOB_NAME]
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'JOB_RUN_ID', 'tabela_origem', 'database_destino'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print('##############################')
print('----- GLUE JOB INITIATED -----')
print('##############################')

dt_load_sot = datetime.now(timezone.utc)
id_execucao = args['JOB_RUN_ID']

sot_transform = SotTransform(spark)

df_bronze = sot_transform.catalog_origem(args["tabela_origem"])

df_validos, df_rej_nulas = sot_transform.separar_chaves_nulas(df_bronze)
df_unicos, df_rej_duplicadas = sot_transform.separar_duplicatas(df_validos)

df_silver = sot_transform.transform(df_unicos, dt_load_sot, id_execucao)
df_rejeitados = df_rej_nulas.unionByName(df_rej_duplicadas)

sot_transform.criar_database(args['database_destino'])

tabela_destino = f"glue_catalog.{args['database_destino']}.transacoes"
tabela_destino_alt = f"glue_catalog.{args['database_destino']}.transacoes_alt"

sot_transform.gravar_tabela_iceberg(df_silver, tabela_destino, '3')
sot_transform.gravar_tabela_iceberg(df_silver, tabela_destino_alt, '2')

print('##############################')
print('------- GLUE JOB DONE -------')
print('##############################')

job.commit()