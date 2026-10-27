import logging
from functools import reduce
from pyspark.sql import Window, DataFrame, SparkSession, functions as F
from pyspark.sql.types import (
    BooleanType,
    DateType,
    DecimalType,
    StringType,
    TimestampType,
)
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SotTransform:
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.COLUNA_PARTICAO = "dt_processamento"
        # A Bronze guarda os dados como chegam; a Silver é a primeira camada com
        # colunas e tipos definidos.
        self.SCHEMA_SILVER = {
            "id_transacao": StringType(),
            "id_contrato": StringType(),
            "id_conta": StringType(),
            "cnpj": StringType(),
            "cod_agencia": StringType(),
            "tipo_contrato": StringType(),
            "tipo_lancamento": StringType(),
            "tipo_produto": StringType(),
            "valor_lancamento": DecimalType(18, 2),
            "dt_lancamento": TimestampType(),
            "dt_processamento": DateType(),
            "cod_cosif": StringType(),
            "flag_estorno": BooleanType(),
            "id_lote": StringType(),
        }
        self.CHAVES_OBRIGATORIAS = ["id_transacao", "id_conta", "id_contrato", "dt_processamento"]
        # Sinal de cada tipo de lançamento; outros tipos são rejeitados.
        self.NATUREZA_LANCAMENTO = {"CREDITO": 1, "DEBITO": -1}

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

    def aplicar_schema(self, df: DataFrame) -> DataFrame:
        """
        Seleciona as colunas de `SCHEMA_SILVER`, na ordem do schema, convertidas
        para os tipos esperados. Colunas da Bronze fora do schema são descartadas.

        Args:
            df (DataFrame): Dados lidos da camada Bronze.

        Returns:
            DataFrame: Dados com exatamente as colunas e os tipos de `SCHEMA_SILVER`.

        Raises:
            ValueError: Se alguma coluna do schema não existir na Bronze.
        """
        colunas_faltantes = set(self.SCHEMA_SILVER) - set(df.columns)
        if colunas_faltantes:
            raise ValueError(
                f"Colunas ausentes na Bronze: {sorted(colunas_faltantes)}"
            )

        return df.select(
            [F.col(nome).cast(tipo).alias(nome) for nome, tipo in self.SCHEMA_SILVER.items()]
        )

    def transform(self, df: DataFrame, dt_load_sot: datetime, id_execucao: str) -> DataFrame:
        """
        Aplica as transformações da camada Silver.

        Args:
            df (DataFrame): Dados lidos da camada Bronze.
            dt_load_sot (datetime): Data e hora da carga Silver.
            id_execucao (str): Identificador da execução do job.

        Returns:
            DataFrame: Dados transformados para a camada Silver.
        """

        df = (
            df.withColumn("tipo_contrato", F.trim(F.upper(F.col("tipo_contrato"))))
            .withColumn("tipo_lancamento", F.trim(F.upper(F.col("tipo_lancamento"))))
            .withColumn("tipo_produto", F.trim(F.upper(F.col("tipo_produto"))))
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
        )

        df = self.calcular_valor_assinado(df)
        return self.adicionar_auditoria(df, dt_load_sot, id_execucao)

    def adicionar_auditoria(self, df: DataFrame, dt_load_sot: datetime, id_execucao: str) -> DataFrame:
        """
        Acrescenta `dt_load_sot` e `id_execucao`, usados nas tabelas da Silver e na quarentena.

        Args:
            df (DataFrame): Dados a gravar.
            dt_load_sot (datetime): Data e hora da carga Silver.
            id_execucao (str): Identificador da execução do job.
        """
        return (
            df.withColumn("dt_load_sot", F.lit(dt_load_sot).cast("timestamp"))
            .withColumn("id_execucao", F.lit(id_execucao))
        )

    @staticmethod
    def ordenar_como_tabela(df: DataFrame, colunas_tabela: list[str]) -> DataFrame:
        """
        Reordena as colunas do DataFrame na ordem da tabela, com as colunas novas no fim.

        O Iceberg recusa gravar quando a ordem das colunas difere da tabela, mesmo com
        evolução de schema; isso acontece quando a origem muda a posição de uma coluna
        ou acrescenta uma coluna no meio.

        Args:
            df: Dados a gravar.
            colunas_tabela: Colunas da tabela existente, na ordem dela.
        """
        existentes = [c for c in colunas_tabela if c in df.columns]
        novas = [c for c in df.columns if c not in colunas_tabela]
        return df.select(existentes + novas)

    def gravar_tabela_iceberg(self, df: DataFrame, tabela_destino: str, versao: str) -> None:
        """
        Cria a tabela Iceberg particionada por `dt_processamento` ou, se ela já existir,
        substitui as partições presentes no DataFrame.

        A tabela aceita evolução de schema: colunas novas são acrescentadas à tabela.

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
                .tableProperty("write.spark.accept-any-schema", "true")
                .partitionedBy(self.COLUNA_PARTICAO)
                .create()
            )
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

    def separar_lancamento_invalido(self, df: DataFrame) -> tuple[DataFrame, DataFrame]:
        """
        Separa os registros cujo `tipo_lancamento` não está em `NATUREZA_LANCAMENTO`,
        como os tipos antigos do gerador (TARIFA, IOF, JUROS). Sem essa separação,
        eles ficariam com `valor_assinado` nulo e sumiriam dos saldos.

        Returns:
            (válidos, rejeitados); os rejeitados têm a coluna `motivo_rejeicao`.
        """
        tipo = F.trim(F.upper(F.col("tipo_lancamento")))
        valido = F.coalesce(tipo.isin(*self.NATUREZA_LANCAMENTO), F.lit(False))

        validos = df.filter(valido)
        rejeitados = df.filter(~valido).withColumn(
            "motivo_rejeicao",
            F.concat(F.lit("tipo_lancamento inválido: "), F.coalesce(F.col("tipo_lancamento"), F.lit("nulo"))),
        )
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
        cliente (CREDITO) e negativo para saída (DEBITO), já considerando o estorno.
        Tipo de lançamento fora de `NATUREZA_LANCAMENTO` fica com valor nulo.
        """
        mapa_sinal = F.create_map(
            *[F.lit(valor) for par in self.NATUREZA_LANCAMENTO.items() for valor in par]
        )
        sinal = mapa_sinal[F.col("tipo_lancamento")]

        estornado = F.coalesce(F.col("flag_estorno"), F.lit(False))
        fator = F.when(estornado, -sinal).otherwise(sinal)

        return df.withColumn(
            "valor_assinado",
            (F.col("valor_lancamento") * fator).cast(DecimalType(18, 2)),
        )
