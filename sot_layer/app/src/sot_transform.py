import logging
from functools import reduce
from pyspark.sql import Window, DataFrame, SparkSession, functions as F

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SotTransform:
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.COLUNA_PARTICAO = "dt_processamento" 
        self.CHAVES_OBRIGATORIAS = ["id_transacao", "id_conta", "id_contrato", "dt_processamento"]

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

    def separar_chaves_nulas(self, df: DataFrame) -> tuple[DataFrame, DataFrame]:
        """
        Separa os registros com alguma chave obrigatória nula ou vazia.

        Returns:
            (válidos, rejeitados); os rejeitados têm a coluna `motivo_rejeicao`.
        """
        tipos = dict(df.dtypes)

        def chave_invalida(coluna: str):
            nula = F.col(coluna).isNull()
            if tipos[coluna] == "string":
                return nula | (F.trim(F.col(coluna)) == "")
            return nula

        condicoes = {c: chave_invalida(c) for c in self.CHAVES_OBRIGATORIAS}
        alguma_invalida = reduce(lambda a, b: a | b, condicoes.values())

        # Lista só as colunas com problema, por exemplo "chave nula: id_conta, id_contrato"
        motivo = F.concat(
            F.lit("chave nula: "),
            F.concat_ws(", ", *[F.when(cond, F.lit(c)) for c, cond in condicoes.items()]),
        )

        validos = df.filter(~alguma_invalida)
        rejeitados = df.filter(alguma_invalida).withColumn("motivo_rejeicao", motivo)
        return validos, rejeitados

    def separar_duplicatas(self, df: DataFrame) -> tuple[DataFrame, DataFrame]:
        """
        Mantém um registro por `id_transacao`, o mais recente, e separa os demais.

        Returns:
            (únicos, duplicados); os duplicados têm a coluna `motivo_rejeicao`.
        """
        # Ordem de preferência: processamento mais recente, depois lançamento
        # mais recente; o id_lote só serve de desempate, para o resultado
        # ser sempre o mesmo.
        janela = Window.partitionBy("id_transacao").orderBy(
            F.col("dt_processamento").desc(),
            F.col("dt_lancamento").desc(),
            F.col("id_lote").desc(),
        )

        df_numerado = df.withColumn("_ordem", F.row_number().over(janela))

        unicos = df_numerado.filter(F.col("_ordem") == 1).drop("_ordem")
        duplicados = (
            df_numerado.filter(F.col("_ordem") > 1)
            .drop("_ordem")
            .withColumn("motivo_rejeicao", F.lit("duplicata de id_transacao"))
        )
        return unicos, duplicados
