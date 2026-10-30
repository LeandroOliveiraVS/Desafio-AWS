from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from business_views.saldo_conta_por_contrato import SaldoContaContrato
from spec_transform import carregar_business_view

SCHEMA_SILVER = (
    "id_contrato string, id_conta string, cod_agencia string, cnpj string, "
    "tipo_contrato string, valor_assinado decimal(18,2), dt_lancamento timestamp"
)


def lancamento(contrato, valor, dt_lancamento, tipo_contrato="CC"):
    conta = contrato.replace("c-", "")
    return (contrato, conta, "0001", f"CNPJ{conta}", tipo_contrato, Decimal(valor), dt_lancamento)


def utc(ano, mes, dia, hora=12):
    return datetime(ano, mes, dia, hora, tzinfo=timezone.utc)


@pytest.fixture
def view(spark):
    return SaldoContaContrato(spark)


def saldos(view, spark, linhas):
    df = spark.createDataFrame(linhas, SCHEMA_SILVER)
    resultado = view.create_business_view(df).orderBy("id_contrato", "data_saldo").collect()
    return [(r.id_contrato, r.data_saldo, r.movimento_dia, r.qtd_lancamentos, r.saldo) for r in resultado]


def test_saldo_acumulado_e_dias_sem_movimento(view, spark):
    resultado = saldos(view, spark, [
        lancamento("c-1", "100.00", utc(2026, 10, 1)),
        lancamento("c-1", "-30.00", utc(2026, 10, 1)),
        lancamento("c-1", "-20.00", utc(2026, 10, 3)),
    ])

    assert resultado == [
        ("c-1", date(2026, 10, 1), Decimal("70.00"), 2, Decimal("70.00")),
        ("c-1", date(2026, 10, 2), Decimal("0.00"), 0, Decimal("70.00")),  # sem movimento
        ("c-1", date(2026, 10, 3), Decimal("-20.00"), 1, Decimal("50.00")),
    ]


def test_todo_contrato_vai_ate_a_data_mais_recente_da_base(view, spark):
    resultado = saldos(view, spark, [
        lancamento("c-1", "10.00", utc(2026, 10, 1)),
        lancamento("c-2", "5.00", utc(2026, 10, 3)),
    ])

    assert [(c, d, s) for c, d, _, _, s in resultado] == [
        ("c-1", date(2026, 10, 1), Decimal("10.00")),
        ("c-1", date(2026, 10, 2), Decimal("10.00")),
        ("c-1", date(2026, 10, 3), Decimal("10.00")),
        ("c-2", date(2026, 10, 3), Decimal("5.00")),
    ]


def test_saldo_mes_reinicia_no_primeiro_dia_do_mes(view, spark):
    df = spark.createDataFrame([
        lancamento("c-1", "100.00", utc(2026, 9, 29)),
        lancamento("c-1", "-30.00", utc(2026, 9, 30)),
        lancamento("c-1", "50.00", utc(2026, 10, 1)),
        lancamento("c-1", "-20.00", utc(2026, 10, 3)),
    ], SCHEMA_SILVER)

    resultado = view.create_business_view(df).orderBy("data_saldo").collect()

    assert [(r.data_saldo, r.saldo_mes, r.saldo) for r in resultado] == [
        (date(2026, 9, 29), Decimal("100.00"), Decimal("100.00")),
        (date(2026, 9, 30), Decimal("70.00"), Decimal("70.00")),
        (date(2026, 10, 1), Decimal("50.00"), Decimal("120.00")),  # novo mês
        (date(2026, 10, 2), Decimal("50.00"), Decimal("120.00")),  # sem movimento
        (date(2026, 10, 3), Decimal("30.00"), Decimal("100.00")),
    ]


def test_considera_apenas_conta_corrente(view, spark):
    resultado = saldos(view, spark, [
        lancamento("c-1", "10.00", utc(2026, 10, 1)),
        lancamento("c-9", "999.00", utc(2026, 10, 1), tipo_contrato="CDB"),
    ])

    assert [c for c, *_ in resultado] == ["c-1"]


def test_data_do_saldo_usa_horario_de_brasilia(view, spark):
    # 2/10 às 01:00 UTC ainda é 1/10 às 22:00 em Brasília.
    resultado = saldos(view, spark, [lancamento("c-1", "10.00", utc(2026, 10, 2, hora=1))])

    assert resultado[0][1] == date(2026, 10, 1)


def test_particiona_por_data_saldo():
    assert SaldoContaContrato.COLUNAS_PARTICAO == ("data_saldo",)


def test_job_encontra_a_view_pelo_nome_do_arquivo(spark):
    view = carregar_business_view("saldo_conta_por_contrato", spark)

    assert isinstance(view, SaldoContaContrato)
