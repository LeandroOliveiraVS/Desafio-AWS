import pytest

from app.src.sot_transform import SotTransform
from pyspark.sql import functions as F
from pyspark.sql import SparkSession

from datetime import date

@pytest.fixture(scope="session")
def spark():
    """Sessão Spark local compartilhada pelos testes."""
    sessao = (
        SparkSession.builder.master("local[1]")
        .appName("testes-raw-transformacoes")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield sessao
    sessao.stop()

def test_separar_chaves_nulas(spark):
    df = spark.createDataFrame(
        [("t-1", "0001", "c-1"), ("t-2", None, "c-2"), ("t-3", " ", None)],
        "id_transacao string, id_conta string, id_contrato string",
    ).withColumn("dt_processamento", F.current_date())

    validos, rejeitados = SotTransform(spark).separar_chaves_nulas(df)

    assert [r.id_transacao for r in validos.collect()] == ["t-1"]
    motivos = {r.id_transacao: r.motivo_rejeicao for r in rejeitados.collect()}
    assert motivos == {
        "t-2": "chave nula: id_conta",
        "t-3": "chave nula: id_conta, id_contrato",
    }

def test_separar_duplicatas_mantem_o_mais_recente(spark):
    df = spark.createDataFrame(
        [
            ("t-1", date(2026, 10, 20), "l-1"),
            ("t-1", date(2026, 10, 21), "l-2"),  # mais recente: fica
            ("t-2", date(2026, 10, 21), "l-2"),
        ],
        "id_transacao string, dt_processamento date, id_lote string",
    ).withColumn("dt_lancamento", F.current_timestamp())

    unicos, duplicados = SotTransform(spark).separar_duplicatas(df)

    assert {(r.id_transacao, r.id_lote) for r in unicos.collect()} == {("t-1", "l-2"), ("t-2", "l-2")}
    assert [(r.id_transacao, r.id_lote, r.motivo_rejeicao) for r in duplicados.collect()] == [
        ("t-1", "l-1", "duplicata de id_transacao")
    ]