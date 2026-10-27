"""
Regras da camada Bronze, sem dependência do `awsglue`.

A Bronze carrega os dados da origem da forma que são, sem selecionar colunas
nem converter tipos. Os métodos recebem e devolvem DataFrames do Spark, o que
permite testá-los com PySpark local e pytest, sem executar o job no Glue.
"""
import logging

from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Bronze:

    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.COLUNA_PARTICAO = "dt_processamento"

    def criar_database(self, database: str) -> None:
        """
        Cria o database no Glue Catalog, caso ainda não exista.

        Args:
            database (str): Nome do database, como `bronze`.
        """
        logger.info("Garantindo a existência do database: %s", database)
        self.spark.sql(f"CREATE DATABASE IF NOT EXISTS glue_catalog.{database}")


    def montar_caminho_origem(self, bucket_origem: str, prefixo: str = "contratos") -> str:
        """
        Monta o caminho S3 de onde os Parquet da origem são lidos.

        Args:
            bucket_origem: Nome do bucket de origem.
            prefixo: Prefixo dos arquivos dentro do bucket.

        Returns:
            Caminho no formato `s3://<bucket>/<prefixo>/`.
        """
        return f"s3://{bucket_origem}/{prefixo.strip('/')}/"


    def ler_origem(self, caminho: str) -> DataFrame:
        """
        Lê todos os Parquet abaixo de `caminho`, como estão na origem.

        Os arquivos podem ter schemas diferentes (por exemplo, arquivos antigos sem
        uma coluna criada depois); o `mergeSchema` junta as colunas de todos eles,
        deixando nulas as colunas que não existem em um arquivo. Sem ele, o Spark
        usaria o schema de um único arquivo e poderia descartar colunas.

        Args:
            caminho: Pasta de origem, como `s3://<bucket>/contratos/`.

        Returns:
            DataFrame com a união das colunas de todos os arquivos.
        """
        logger.info("Lendo dados da origem: %s", caminho)
        return (
            self.spark.read
            .option("mergeSchema", "true")
            .option("recursiveFileLookup", "true")
            .parquet(caminho)
        )


    def gravar_tabela_iceberg(
        self,
        df: DataFrame,
        nome_tabela: str,
        format_version: str,
    ) -> None:
        """
        Cria a tabela Iceberg particionada por `dt_processamento` ou, se ela já existir,
        substitui as partições presentes no DataFrame.

        A tabela aceita evolução de schema: colunas novas na origem são acrescentadas
        à tabela, e colunas ausentes no DataFrame ficam nulas.

        Args:
            df: DataFrame lido da origem.
            nome_tabela: Nome completo da tabela, como `glue_catalog.bronze.transacoes`.
            format_version: Versão do formato Iceberg usada na criação ("2" ou "3").
        """
        if not self.spark.catalog.tableExists(nome_tabela):
            logger.info(
                "Tabela %s não encontrada. Criando tabela Iceberg V%s "
                "com partição por %s.",
                nome_tabela,
                format_version,
                self.COLUNA_PARTICAO,
            )
            (
                df.writeTo(nome_tabela)
                .using("iceberg")
                .tableProperty("format-version", format_version)
                .tableProperty("write.spark.accept-any-schema", "true")
                .partitionedBy(self.COLUNA_PARTICAO)
                .create()
            )
        else:
            logger.info(
                "Tabela %s já existe. Iniciando substituição das "
                "partições presentes nos dados.",
                nome_tabela,
            )
            # Garante a evolução de schema também em tabelas criadas antes dela.
            self.spark.sql(
                f"ALTER TABLE {nome_tabela} "
                "SET TBLPROPERTIES ('write.spark.accept-any-schema' = 'true')"
            )
            df.writeTo(nome_tabela).option("mergeSchema", "true").overwritePartitions()
