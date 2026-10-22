import logging
from functools import reduce
from pyspark.sql import Window, DataFrame, SparkSession, functions as F
from pyspark.sql.types import DecimalType
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SotTransform:
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.COLUNA_PARTICAO = "dt_processamento" 
        self.CHAVES_OBRIGATORIAS = ["id_transacao", "id_conta", "id_contrato", "dt_processamento"]
        # Valores negativos são cobrança.
        self.NATUREZA_LANCAMENTO = {"CREDITO": 1, "DEBITO": -1, "TARIFA": -1, "IOF": -1}
        # Contratos em que JUROS é rendimento pago ao cliente; nos demais, é cobrança.
        self.CONTRATOS_JUROS_CREDITADOS = ["POUP", "CDB", "LCI"]
        self.CATEGORIA_PRODUTO = {
            "CC": "CONTA",
            "POUP": "CONTA",
            "CDB": "INVESTIMENTO",
            "LCI": "INVESTIMENTO",
            "SEGURO": "SEGURO",
            "CONSORCIO": "CONSORCIO",
        }
        # Fuso usado no ano_mes; considera a sessão Spark em UTC (padrão do Glue).
        self.FUSO_HORARIO = "America/Sao_Paulo"

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

    def transform(self, df: DataFrame, dt_load_sot: datetime, id_execucao: str) -> DataFrame:
        """
        Aplica as transformações da camada Silver.

        Args:
            df (DataFrame): Dados lidos da camada Bronze.

        Returns:
            DataFrame: Dados transformados para a camada Silver.
        """

        df = (
            df.withColumn("tipo_contrato", F.trim(F.upper(F.col("tipo_contrato"))))
            .withColumn("tipo_lancamento", F.trim(F.upper(F.col("tipo_lancamento"))))
            .withColumn("cod_cosif", F.trim(F.upper(F.col("cod_cosif"))))
        )

        # Contrato sem categoria mapeada fica com categoria nula.
        mapa_categoria = F.create_map(
            *[F.lit(valor) for par in self.CATEGORIA_PRODUTO.items() for valor in par]
        )

        df = (
            df.withColumn("categoria_produto", mapa_categoria[F.col("tipo_contrato")])
            # Mês do lançamento no horário de Brasília, como "2026-10".
            .withColumn(
                "ano_mes",
                F.date_format(
                    F.from_utc_timestamp(F.col("dt_lancamento"), self.FUSO_HORARIO), "yyyy-MM"
                ),
            )
            # dt_processamento é definido em UTC, então a comparação também usa UTC.
            .withColumn(
                "dias_ate_processamento",
                F.datediff(F.col("dt_processamento"), F.to_date(F.col("dt_lancamento"))),
            )
            .withColumn("dt_load_sot", F.lit(dt_load_sot).cast("timestamp"))
            .withColumn("id_execucao", F.lit(id_execucao))
        )

        return self.calcular_valor_assinado(df)

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

    def calcular_valor_assinado(self, df: DataFrame) -> DataFrame:
        """
        Cria `valor_assinado`: positivo para entrada de dinheiro na conta do
        cliente e negativo para saída, já considerando o estorno.
        """
        lancamento = F.col("tipo_lancamento")
        contrato = F.col("tipo_contrato")

        sinal = F.when(
            lancamento == "JUROS",
            F.when(contrato.isin(*self.CONTRATOS_JUROS_CREDITADOS), F.lit(1)).otherwise(F.lit(-1)),
        )
        for tipo, valor_sinal in self.NATUREZA_LANCAMENTO.items():
            sinal = sinal.when(lancamento == tipo, F.lit(valor_sinal))

        estornado = F.coalesce(F.col("flag_estorno"), F.lit(False))
        fator = F.when(estornado, -sinal).otherwise(sinal)

        return df.withColumn(
            "valor_assinado",
            (F.col("valor_lancamento") * fator).cast(DecimalType(18, 2)),
        )