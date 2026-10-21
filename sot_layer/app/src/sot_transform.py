import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col

logger = logging.getLogger(__name__)

class SotTransform:
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.COLUNA_PARTICAO = "dt_processamento"

    def catalog_origem(self, tabela_origem: str) -> DataFrame:
        """
        Reads the source table from the Glue Catalog.

        Args:
            tabela_origem (str): Name of the source table.

        Returns:
            DataFrame: DataFrame containing the data from the source table.
        """
        logger.info(f"Lendo tabela de origem: {tabela_origem}")
        df = self.spark.table(tabela_origem)
        return df

    def transform(self, df: DataFrame) -> DataFrame:
        """
        Transforms the input DataFrame by selecting specific columns and renaming them.

        Args:
            df (DataFrame): Input DataFrame to be transformed.
        """

    def gravar_tabela_iceberg(self, df: DataFrame, tabela_destino: str, versao: str) -> None:
        """
        Writes the DataFrame to an Iceberg table in the Glue Catalog.

        Args:
            df (DataFrame): DataFrame to be written.
            tabela_destino (str): Name of the destination table.
            versao (str): Version of the Iceberg table (e.g., "3" for V3).
        """
        logger.info(f"Gravando tabela Iceberg {versao} no Glue Catalog: {tabela_destino}")
        df.writeTo(tabela_destino).tableProperty("format-version", versao).createOrReplace()