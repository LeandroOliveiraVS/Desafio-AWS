import sys

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

from sot_transform import SotTransform

## @params: [JOB_NAME]
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'tabela_origem', 'database_destino'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print('##############################')
print('----- GLUE JOB INITIATED -----')
print('##############################')

df_bronze = SotTransform(spark).catalog_origem(args["tabela_origem"])

df_silver = SotTransform(spark).transform(df_bronze)

tabela_destino = f"{args['database_destino']}.transacoes"
tabela_destino_alt = f"{args['database_destino']}.transacoes_alt"

SotTransform(spark).gravar_tabela_iceberg(df_silver, tabela_destino, '3')
SotTransform(spark).gravar_tabela_iceberg(df_silver, tabela_destino_alt, '2')

print('##############################')
print('------- GLUE JOB DONE -------')
print('##############################')

job.commit()