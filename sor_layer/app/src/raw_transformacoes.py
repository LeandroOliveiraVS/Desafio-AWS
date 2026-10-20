"""
Regras da camada Bronze, sem dependência do `awsglue`.

As funções recebem e devolvem DataFrames do Spark, o que permite testá-las
com PySpark local e pytest, sem executar o job no Glue.
"""
import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col
from pyspark.sql.types import (
    BooleanType,
    DateType,
    DecimalType,
    StringType,
    TimestampType,
)

logger = logging.getLogger(__name__)

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

COLUNA_PARTICAO = "dt_processamento"


def montar_caminho_origem(bucket_origem: str, prefixo: str = "contratos") -> str:
    """
    Monta o caminho S3 de onde os Parquet da origem são lidos.

    Args:
        bucket_origem: Nome do bucket de origem.
        prefixo: Prefixo dos arquivos dentro do bucket.

    Returns:
        Caminho no formato `s3://<bucket>/<prefixo>/`.
    """
    return f"s3://{bucket_origem}/{prefixo.strip('/')}/"


def aplicar_contrato(df: DataFrame) -> DataFrame:
    """
    Seleciona as colunas do contrato, na ordem do contrato, convertidas para os tipos esperados.

    Colunas que não fazem parte do contrato são descartadas.

    Args:
        df: DataFrame lido da origem.

    Returns:
        DataFrame com exatamente as colunas e os tipos de `SCHEMA_CONTRATO`.

    Raises:
        ValueError: Se alguma coluna do contrato não existir na origem.
    """
    colunas_faltantes = set(SCHEMA_CONTRATO) - set(df.columns)
    if colunas_faltantes:
        raise ValueError(
            f"Colunas do contrato ausentes na origem: {sorted(colunas_faltantes)}"
        )

    return df.select(
        [col(nome).cast(tipo).alias(nome) for nome, tipo in SCHEMA_CONTRATO.items()]
    )


def gravar_tabela_iceberg(
    spark: SparkSession,
    df: DataFrame,
    nome_tabela: str,
    format_version: str,
) -> None:
    """
    Cria a tabela Iceberg particionada por `dt_processamento` ou, se ela já existir,
    substitui as partições presentes no DataFrame.

    Args:
        spark: Sessão Spark com o catálogo Iceberg configurado.
        df: DataFrame já com o contrato aplicado.
        nome_tabela: Nome completo da tabela, como `glue_catalog.bronze.transacoes`.
        format_version: Versão do formato Iceberg usada na criação ("2" ou "3").
    """
    if not spark.catalog.tableExists(nome_tabela):
        logger.info(
            "Tabela %s não encontrada. Criando tabela Iceberg V%s "
            "com partição por %s.",
            nome_tabela,
            format_version,
            COLUNA_PARTICAO,
        )
        (
            df.writeTo(nome_tabela)
            .using("iceberg")
            .tableProperty("format-version", format_version)
            .partitionedBy(COLUNA_PARTICAO)
            .create()
        )
    else:
        logger.info(
            "Tabela %s já existe. Iniciando substituição das "
            "partições presentes nos dados.",
            nome_tabela,
        )
        df.writeTo(nome_tabela).overwritePartitions()
