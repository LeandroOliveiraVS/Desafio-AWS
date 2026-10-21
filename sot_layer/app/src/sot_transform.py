import logging

from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SotTransform:
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.COLUNA_PARTICAO = "dt_processamento"

    def criar_database(self, database: str) -> None:
        """
        Cria o database no Glue Catalog, caso ainda não exista.

        Args:
            database (str): Nome do database, como `silver`.
        """
        logger.info("Garantindo a existência do database: %s", database)
        self.spark.sql(f"CREATE DATABASE IF NOT EXISTS glue_catalog.{database}")

    def catalog_origem(self, tabela_origem: str) -> DataFrame:
        """
        Lê a tabela de origem pelo Glue Catalog.

        Args:
            tabela_origem (str): Nome completo da tabela, como `glue_catalog.bronze.transacoes`.

        Returns:
            DataFrame: Dados da tabela de origem.
        """
        logger.info("Lendo tabela de origem: %s", tabela_origem)
        df = self.spark.table(tabela_origem)
        return df

    def transform(self, df: DataFrame) -> DataFrame:
        """
        Aplica as transformações da camada Silver.

        Args:
            df (DataFrame): Dados lidos da camada Bronze.

        Returns:
            DataFrame: Dados transformados para a camada Silver.
        """
        # TODO: implementar as transformações da Silver.
        return df

    def gravar_tabela_iceberg(self, df: DataFrame, tabela_destino: str, versao: str) -> None:
        """
        Cria a tabela Iceberg particionada por `dt_processamento` ou, se ela já existir,
        substitui as partições presentes no DataFrame.

        Args:
            df (DataFrame): Dados a serem gravados.
            tabela_destino (str): Nome completo da tabela de destino.
            versao (str): Versão do formato Iceberg usada na criação ("2" ou "3").
        """
        logger.info("Gravando tabela Iceberg V%s no Glue Catalog: %s", versao, tabela_destino)
        if not self.spark.catalog.tableExists(tabela_destino):
            logger.info(
                "Tabela %s não encontrada. Criando tabela Iceberg V%s "
                "com partição por %s.",
                tabela_destino,
                versao,
                self.COLUNA_PARTICAO,
            )
            (
                df.writeTo(tabela_destino)
                .using("iceberg")
                .tableProperty("format-version", versao)
                .partitionedBy(self.COLUNA_PARTICAO)
                .create()
            )
        else:
            logger.info(
                "Tabela %s já existe. Iniciando substituição das "
                "partições presentes nos dados.",
                tabela_destino,
            )
            df.writeTo(tabela_destino).overwritePartitions()
