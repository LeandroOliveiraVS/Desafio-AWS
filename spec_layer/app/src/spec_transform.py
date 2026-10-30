"""
Base das business views da camada Gold (spec).

Cada business view fica em um arquivo próprio dentro do pacote `business_views`,
herda `SpecTransform` e implementa `create_business_view`.
"""
import importlib
import inspect
import logging
from abc import ABC, abstractmethod

from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SpecTransform(ABC):
    """
    Classe base das business views.

    Attributes:
        COLUNAS_PARTICAO: Colunas de partição das tabelas da view. Uma business view
            pode sobrescrever o valor; uma tupla vazia cria a tabela sem partição e,
            nesse caso, cada execução substitui a tabela inteira.
    """

    COLUNAS_PARTICAO: tuple[str, ...] = ("dt_processamento",)

    def __init__(self, spark: SparkSession):
        self.spark = spark

    def criar_database(self, database: str) -> None:
        """
        Cria o database no Glue Catalog, caso ainda não exista.

        Args:
            database (str): Nome do database, como `gold`.
        """
        logger.info("Garantindo a existência do database: %s", database)
        self.spark.sql(f"CREATE DATABASE IF NOT EXISTS glue_catalog.{database}")

    def catalog_origem(self, tabela_origem: str) -> DataFrame:
        """
        Lê uma tabela pelo Glue Catalog.

        Também pode ser usada dentro de `create_business_view` para ler outras
        tabelas da Silver e fazer joins.

        Args:
            tabela_origem (str): Nome completo da tabela, como `glue_catalog.silver.transacoes`.

        Returns:
            DataFrame: Dados da tabela.
        """
        logger.info("Lendo tabela de origem: %s", tabela_origem)
        return self.spark.table(tabela_origem)

    @abstractmethod
    def create_business_view(self, df: DataFrame) -> DataFrame:
        """
        Aplica as regras de negócio da view sobre os dados da camada Silver.

        Args:
            df (DataFrame): Dados lidos da tabela de origem.

        Returns:
            DataFrame: Dados da business view, contendo as `COLUNAS_PARTICAO`.
        """

    @staticmethod
    def ordenar_como_tabela(df: DataFrame, colunas_tabela: list[str]) -> DataFrame:
        """
        Reordena as colunas do DataFrame na ordem da tabela, com as colunas novas no fim.

        O Iceberg recusa gravar quando a ordem das colunas difere da tabela, mesmo com
        evolução de schema.

        Args:
            df: Dados a gravar.
            colunas_tabela: Colunas da tabela existente, na ordem dela.
        """
        existentes = [c for c in colunas_tabela if c in df.columns]
        novas = [c for c in df.columns if c not in colunas_tabela]
        return df.select(existentes + novas)

    def gravar_tabela_iceberg(self, df: DataFrame, tabela_destino: str, versao: str) -> None:
        """
        Cria a tabela Iceberg particionada por `COLUNAS_PARTICAO` ou, se ela já existir,
        substitui as partições presentes no DataFrame.

        A tabela aceita evolução de schema: colunas novas são acrescentadas à tabela.

        Args:
            df (DataFrame): Dados a serem gravados.
            tabela_destino (str): Nome completo da tabela de destino.
            versao (str): Versão do formato Iceberg usada na criação ("2" ou "3").

        Raises:
            ValueError: Se alguma coluna de partição não existir no DataFrame.
        """
        colunas_faltantes = [c for c in self.COLUNAS_PARTICAO if c not in df.columns]
        if colunas_faltantes:
            raise ValueError(
                f"Colunas de partição ausentes na business view: {colunas_faltantes}"
            )

        logger.info("Gravando tabela Iceberg V%s no Glue Catalog: %s", versao, tabela_destino)
        if not self.spark.catalog.tableExists(tabela_destino):
            logger.info(
                "Tabela %s não encontrada. Criando tabela Iceberg V%s "
                "com partição por %s.",
                tabela_destino,
                versao,
                list(self.COLUNAS_PARTICAO),
            )
            writer = (
                df.writeTo(tabela_destino)
                .using("iceberg")
                .tableProperty("format-version", versao)
                .tableProperty("write.spark.accept-any-schema", "true")
            )
            if self.COLUNAS_PARTICAO:
                writer = writer.partitionedBy(*self.COLUNAS_PARTICAO)
            writer.create()
        else:
            logger.info(
                "Tabela %s já existe. Iniciando substituição das "
                "partições presentes nos dados.",
                tabela_destino,
            )
            # Garante a evolução de schema também em tabelas criadas antes dela.
            self.spark.sql(
                f"ALTER TABLE {tabela_destino} "
                "SET TBLPROPERTIES ('write.spark.accept-any-schema' = 'true')"
            )
            df = self.ordenar_como_tabela(df, self.spark.table(tabela_destino).columns)
            df.writeTo(tabela_destino).option("mergeSchema", "true").overwritePartitions()


def carregar_business_view(
    nome: str,
    spark: SparkSession,
    pacote: str = "business_views",
) -> SpecTransform:
    """
    Importa `<pacote>.<nome>` e instancia a business view definida nele.

    Args:
        nome (str): Nome do arquivo da view, sem `.py`. Também é o nome da tabela Gold.
        spark (SparkSession): Sessão Spark repassada para a view.
        pacote (str): Pacote onde ficam as business views.

    Returns:
        SpecTransform: Instância da business view.

    Raises:
        ValueError: Se o nome for inválido, o arquivo não existir ou o módulo não
            definir exatamente uma subclasse concreta de `SpecTransform`.
    """
    if not nome.isidentifier():
        raise ValueError(f"Nome de business view inválido: {nome!r}")

    nome_modulo = f"{pacote}.{nome}"
    try:
        modulo = importlib.import_module(nome_modulo)
    except ModuleNotFoundError as erro:
        if erro.name in (pacote, nome_modulo):
            raise ValueError(
                f"Business view {nome!r} não encontrada no pacote {pacote!r}."
            ) from erro
        raise

    classes = [
        classe
        for _, classe in inspect.getmembers(modulo, inspect.isclass)
        if issubclass(classe, SpecTransform)
        and classe.__module__ == modulo.__name__
        and not inspect.isabstract(classe)
    ]
    if len(classes) != 1:
        raise ValueError(
            f"O módulo {nome_modulo} deve definir exatamente uma business view "
            f"(subclasse de SpecTransform); encontradas: {[c.__name__ for c in classes]}"
        )

    logger.info("Business view carregada: %s.%s", nome_modulo, classes[0].__name__)
    return classes[0](spark)
