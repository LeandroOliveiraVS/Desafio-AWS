import sys
from datetime import datetime, timezone
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame

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

dt_load_sot = datetime.now(timezone.utc)
id_execucao = args['JOB_RUN_ID']

sot_transform = SotTransform(spark)

df_bronze = sot_transform.catalog_origem(args["tabela_origem"])

# A Bronze guarda os dados como chegam; aqui eles ganham colunas e tipos definidos.
df_origem = sot_transform.aplicar_schema(df_bronze)

# Regras de qualidade, nesta ordem; cada etapa separa os registros rejeitados.
df_validos, df_rej_nulas = sot_transform.separar_chaves_nulas(df_origem)
df_tipos_validos, df_rej_tipo = sot_transform.separar_lancamento_invalido(df_validos)
df_unicos, df_rej_duplicadas = sot_transform.separar_duplicatas(df_tipos_validos)

# Em cache: o resultado é usado pelo Data Quality e pelas duas gravações.
df_silver = sot_transform.transform(df_unicos, dt_load_sot, id_execucao).cache()
df_rejeitados = sot_transform.adicionar_auditoria(
    df_rej_nulas.unionByName(df_rej_tipo).unionByName(df_rej_duplicadas),
    dt_load_sot,
    id_execucao,
)

# Data Quality: só monitora. Avalia as regras sobre os dados que serão gravados
# na Silver e publica o resultado no Glue Data Quality e no CloudWatch; uma regra
# com falha, ou um erro na própria avaliação, gera alerta no log, mas não impede
# a gravação.
try:
    from awsgluedq.transforms import EvaluateDataQuality

    resultado_dq = EvaluateDataQuality.apply(
        frame=DynamicFrame.fromDF(df_silver, glueContext, "silver_transacoes"),
        ruleset=sot_transform.regras_data_quality(),
        publishing_options={
            "dataQualityEvaluationContext": "silver_transacoes",
            "enableDataQualityCloudWatchMetrics": True,
            "enableDataQualityResultsPublishing": True,
        },
    ).toDF()

    resultado_dq.select("Rule", "Outcome", "FailureReason").show(truncate=False)
    for falha in resultado_dq.filter("Outcome != 'Passed'").collect():
        print(f"[DATA QUALITY] Regra com falha: {falha['Rule']} | {falha['FailureReason']}")
except Exception as erro:
    print(f"[DATA QUALITY] Avaliação não executada: {erro!r}")

sot_transform.criar_database(args['database_destino'])

tabela_destino = f"glue_catalog.{args['database_destino']}.transacoes"
tabela_destino_alt = f"glue_catalog.{args['database_destino']}.transacoes_alt"
tabela_destino_rejeitados = f"glue_catalog.{args['database_destino']}.transacoes_rejeitadas"

sot_transform.gravar_tabela_iceberg(df_silver, tabela_destino, '3')
sot_transform.gravar_tabela_iceberg(df_silver, tabela_destino_alt, '2')
sot_transform.gravar_tabela_iceberg(df_rejeitados, tabela_destino_rejeitados, '2')

print('##############################')
print('------- GLUE JOB DONE -------')
print('##############################')

job.commit()