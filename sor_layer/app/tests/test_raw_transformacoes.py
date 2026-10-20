from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import DecimalType

from sor_layer.app.src.raw_transformacoes import (
    SCHEMA_CONTRATO,
    aplicar_contrato,
    montar_caminho_origem,
)


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


def test_montar_caminho_origem():
    assert montar_caminho_origem("bucket") == "s3://bucket/contratos/"
    assert montar_caminho_origem("bucket", "/outro/") == "s3://bucket/outro/"


def test_aplicar_contrato_retorna_colunas_e_tipos_do_contrato(spark, registro_origem):
    df = spark.createDataFrame([registro_origem])

    resultado = aplicar_contrato(df)

    assert resultado.columns == list(SCHEMA_CONTRATO)
    assert {campo.name: campo.dataType for campo in resultado.schema} == SCHEMA_CONTRATO


def test_aplicar_contrato_preserva_valores(spark, registro_origem):
    df = spark.createDataFrame([registro_origem])

    linha = aplicar_contrato(df).first()

    assert linha["valor_lancamento"] == Decimal("1234.56")
    assert linha["id_conta"] == "0003"
    assert linha["dt_processamento"] == date(2026, 10, 20)


def test_aplicar_contrato_converte_double_para_decimal(spark, registro_origem):
    """Arquivos antigos do gerador gravavam valor_lancamento como double."""
    registro_origem["valor_lancamento"] = 10.1
    df = spark.createDataFrame([registro_origem])

    resultado = aplicar_contrato(df)

    assert resultado.schema["valor_lancamento"].dataType == DecimalType(18, 2)
    assert resultado.first()["valor_lancamento"] == Decimal("10.10")


def test_aplicar_contrato_descarta_colunas_fora_do_contrato(spark, registro_origem):
    registro_origem["coluna_extra"] = "x"
    df = spark.createDataFrame([registro_origem])

    resultado = aplicar_contrato(df)

    assert "coluna_extra" not in resultado.columns


def test_aplicar_contrato_falha_sem_coluna_obrigatoria(spark, registro_origem):
    """Arquivos antigos do gerador não tinham a coluna cnpj."""
    del registro_origem["cnpj"]
    df = spark.createDataFrame([registro_origem])

    with pytest.raises(ValueError, match="cnpj"):
        aplicar_contrato(df)
