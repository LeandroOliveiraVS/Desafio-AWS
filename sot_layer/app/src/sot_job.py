import sys

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

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



print('##############################')
print('------- GLUE JOB DONE -------')
print('##############################')

job.commit()