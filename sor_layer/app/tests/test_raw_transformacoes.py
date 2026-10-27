from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import DecimalType

from sor_layer.app.src.raw_transformacoes import Bronze


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


@pytest.fixture
def bronze(spark):
    return Bronze(spark)


@pytest.fixture
def registro_origem():
    """Registro como os gravados pela Lambda geradora."""
    return {
        "id_transacao": "t-1",
        "id_contrato": "c-1",
        "id_conta": "0003",
        "cod_agencia": "0001",
        "cnpj": "0L8KQFJRQH9QW",
        "tipo_contrato": "CC",
        "tipo_lancamento": "DEBITO",
        "valor_lancamento": Decimal("1234.56"),
        "dt_lancamento": datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc),
        "dt_processamento": date(2026, 10, 20),
        "cod_cosif": "COSIF-MOCK-001",
        "flag_estorno": False,
        "id_lote": "l-1",
    }


def test_montar_caminho_origem(bronze):
    assert bronze.montar_caminho_origem("bucket") == "s3://bucket/contratos/"
    assert bronze.montar_caminho_origem("bucket", "/outro/") == "s3://bucket/outro/"


def test_ler_origem_junta_colunas_de_arquivos_com_schemas_diferentes(spark, bronze, registro_origem, tmp_path):
    """Arquivos antigos não têm tipo_produto; a coluna não pode ser descartada."""
    antigo = dict(registro_origem, id_transacao="t-antigo")
    novo = dict(registro_origem, id_transacao="t-novo", tipo_produto="PIX_RECEBIDO")
    spark.createDataFrame([antigo]).write.parquet(str(tmp_path / "2026/10/20/09"))
    spark.createDataFrame([novo]).write.parquet(str(tmp_path / "2026/10/27/09"))

    df = bronze.ler_origem(str(tmp_path))

    assert "tipo_produto" in df.columns
    produtos = {r.id_transacao: r.tipo_produto for r in df.collect()}
    assert produtos == {"t-antigo": None, "t-novo": "PIX_RECEBIDO"}


def test_ler_origem_mantem_os_dados_como_estao(spark, bronze, registro_origem, tmp_path):
    """A Bronze não converte tipos nem descarta colunas."""
    registros = [
        dict(registro_origem, coluna_extra="x"),
        dict(registro_origem, coluna_extra="y", id_transacao=None),  # chave nula é mantida
    ]
    origem = spark.createDataFrame(registros)
    origem.write.parquet(str(tmp_path / "2026/10/20/09"))

    df = bronze.ler_origem(str(tmp_path))

    assert set(df.columns) == set(origem.columns)
    assert dict(df.dtypes) == dict(origem.dtypes)
    linhas = {r.coluna_extra: r.id_transacao for r in df.collect()}
    assert linhas == {"x": "t-1", "y": None}


def test_ordenar_como_tabela_segue_a_tabela_e_poe_colunas_novas_no_fim(spark):
    """A ordem que causou o erro na Bronze: cnpj/cod_agencia trocados e coluna nova no meio."""
    df = spark.createDataFrame(
        [("t-1", "0001", "CNPJ", "CREDITO", "PIX_RECEBIDO")],
        "id_transacao string, cod_agencia string, cnpj string, tipo_lancamento string, tipo_produto string",
    )

    resultado = Bronze.ordenar_como_tabela(df, ["id_transacao", "cnpj", "cod_agencia", "tipo_lancamento"])

    assert resultado.columns == ["id_transacao", "cnpj", "cod_agencia", "tipo_lancamento", "tipo_produto"]
    assert resultado.first()["cnpj"] == "CNPJ"
