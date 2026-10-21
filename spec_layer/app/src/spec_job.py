import sys

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

from spec_transform import carregar_business_view

## @params: [JOB_NAME]
args = getResolvedOptions(
    sys.argv, ['JOB_NAME', 'tabela_origem', 'database_destino', 'business_view']
)

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print('##############################')
print('----- GLUE JOB INITIATED -----')
print('##############################')

business_view = carregar_business_view(args['business_view'], spark)

df_silver = business_view.catalog_origem(args['tabela_origem'])

df_gold = business_view.create_business_view(df_silver)

business_view.criar_database(args['database_destino'])

tabela_destino = f"glue_catalog.{args['database_destino']}.{args['business_view']}"
tabela_destino_alt = f"{tabela_destino}_alt"

business_view.gravar_tabela_iceberg(df_gold, tabela_destino, '3')
# Versão V2 para leitura pelo Athena, que não suporta Iceberg V3.
business_view.gravar_tabela_iceberg(df_gold, tabela_destino_alt, '2')

print('##############################')
print('------- GLUE JOB DONE -------')
print('##############################')

job.commit()
