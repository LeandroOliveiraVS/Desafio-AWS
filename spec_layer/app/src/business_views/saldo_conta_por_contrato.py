import logging

from pyspark.sql import DataFrame, Window, functions as F
from pyspark.sql.types import DecimalType

from spec_transform import SpecTransform

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SaldoContaContrato(SpecTransform):
    """
    Business view de saldo diário consolidado da conta corrente (CC) por contrato.

    Gera uma linha por contrato e por dia, do primeiro lançamento do contrato até
    a data mais recente da base, inclusive nos dias sem movimento (o saldo do dia
    anterior se mantém). O saldo é a soma acumulada do `valor_assinado` da Silver;
    como a origem não informa saldo inicial, todo contrato começa com saldo zero.

    A view é recalculada por completo a cada execução, porque a Silver recebe
    lançamentos com atraso que alteram saldos de dias anteriores.
    """

    COLUNAS_PARTICAO = ("data_saldo",)

    TIPO_CONTRATO = "CC"
    # Mesmo fuso usado no `ano_mes` da Silver.
    FUSO_HORARIO = "America/Sao_Paulo"
    CHAVES_CONTRATO = ["id_contrato", "id_conta", "cod_agencia", "cnpj"]

    def create_business_view(self, df: DataFrame) -> DataFrame:
        """
        Calcula o saldo diário de cada contrato de conta corrente.

        Args:
            df (DataFrame): Tabela `silver.transacoes`.

        Returns:
            DataFrame: Uma linha por contrato e `data_saldo`, com o movimento do
            dia, a quantidade de lançamentos e o saldo acumulado.
        """
        movimentos = (
            df.filter(F.col("tipo_contrato") == self.TIPO_CONTRATO)
            .withColumn(
                "data_saldo",
                F.to_date(F.from_utc_timestamp(F.col("dt_lancamento"), self.FUSO_HORARIO)),
            )
            .groupBy(*self.CHAVES_CONTRATO, "data_saldo")
            .agg(
                F.sum("valor_assinado").alias("movimento_dia"),
                F.count(F.lit(1)).alias("qtd_lancamentos"),
            )
        )

        # Calendário: cada contrato, do seu primeiro dia com movimento até a
        # data mais recente da base.
        data_referencia = movimentos.agg(F.max("data_saldo").alias("data_referencia"))
        calendario = (
            movimentos.groupBy(*self.CHAVES_CONTRATO)
            .agg(F.min("data_saldo").alias("data_inicio"))
            .crossJoin(data_referencia)
            .withColumn(
                "data_saldo",
                F.explode(F.sequence("data_inicio", "data_referencia", F.expr("INTERVAL 1 DAY"))),
            )
            .drop("data_inicio", "data_referencia")
        )

        acumulado = (
            Window.partitionBy("id_contrato")
            .orderBy("data_saldo")
            .rowsBetween(Window.unboundedPreceding, Window.currentRow)
        )

        return (
            calendario.join(movimentos, [*self.CHAVES_CONTRATO, "data_saldo"], "left")
            .withColumn(
                "movimento_dia",
                F.coalesce(F.col("movimento_dia"), F.lit(0)).cast(DecimalType(18, 2)),
            )
            .withColumn("qtd_lancamentos", F.coalesce(F.col("qtd_lancamentos"), F.lit(0)))
            .withColumn(
                "saldo",
                F.sum("movimento_dia").over(acumulado).cast(DecimalType(18, 2)),
            )
            .select(
                "data_saldo",
                *self.CHAVES_CONTRATO,
                "movimento_dia",
                "qtd_lancamentos",
                "saldo",
            )
        )
