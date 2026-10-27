import pytest
from decimal import Decimal
from sot_layer.app.src.sot_transform import SotTransform
from pyspark.sql import functions as F
from pyspark.sql import SparkSession

from datetime import date, datetime, timezone

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

@pytest.mark.parametrize(
    "lancamento, contrato, estorno, esperado",
    [
        ("CREDITO", "CC", False, Decimal("10.00")),
        ("DEBITO", "CC", False, Decimal("-10.00")),
        ("CREDITO", "CDB", True, Decimal("-10.00")),  # crédito estornado sai da conta
        ("DEBITO", "CC", True, Decimal("10.00")),   # débito estornado devolve o dinheiro
        ("TARIFA", "CC", False, None),              # tipo fora da natureza: sem sinal
    ],
)
def test_calcular_valor_assinado(spark, lancamento, contrato, estorno, esperado):
    df = spark.createDataFrame(
        [(lancamento, contrato, estorno, Decimal("10.00"))],
        "tipo_lancamento string, tipo_contrato string, flag_estorno boolean, valor_lancamento decimal(18,2)",
    )

    linha = SotTransform(spark).calcular_valor_assinado(df).first()

    assert linha.valor_assinado == esperado


# Valores de auditoria fixos para os testes do transform.
DT_LOAD_SOT = datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)
ID_EXECUCAO = "jr_teste"


def criar_df_transform(spark, registros):
    return spark.createDataFrame(
        registros,
        "tipo_contrato string, tipo_lancamento string, tipo_produto string, cod_cosif string, "
        "flag_estorno boolean, valor_lancamento decimal(18,2), "
        "dt_lancamento timestamp, dt_processamento date",
    )


def test_transform_categoria_produto(spark):
    df = criar_df_transform(
        spark,
        [
            (contrato, "CREDITO", "PIX_RECEBIDO", "X", False, Decimal("1.00"),
             datetime(2026, 10, 20, 12, tzinfo=timezone.utc), date(2026, 10, 20))
            for contrato in [" cc", "POUP", "CDB", "LCI", "SEGURO", "CONSORCIO", "OUTRO"]
        ],
    )

    resultado = {r.tipo_contrato: r.categoria_produto for r in SotTransform(spark).transform(df, DT_LOAD_SOT, ID_EXECUCAO).collect()}

    assert resultado == {
        "CC": "CONTA",
        "POUP": "CONTA",
        "CDB": "INVESTIMENTO",
        "LCI": "INVESTIMENTO",
        "SEGURO": "SEGURO",
        "CONSORCIO": "CONSORCIO",
        "OUTRO": None,
    }


def test_transform_ano_mes_usa_horario_de_brasilia(spark):
    df = criar_df_transform(
        spark,
        [
            # 1/11 às 01:00 UTC ainda é 31/10 às 22:00 em Brasília.
            ("CC", "CREDITO", "PIX_RECEBIDO", "X", False, Decimal("1.00"),
             datetime(2026, 11, 1, 1, tzinfo=timezone.utc), date(2026, 11, 1)),
            ("CC", "CREDITO", "PIX_RECEBIDO", "X", False, Decimal("1.00"),
             datetime(2026, 11, 1, 12, tzinfo=timezone.utc), date(2026, 11, 1)),
        ],
    )

    resultado = [r.ano_mes for r in SotTransform(spark).transform(df, DT_LOAD_SOT, ID_EXECUCAO).orderBy("dt_lancamento").collect()]

    assert resultado == ["2026-10", "2026-11"]


def test_transform_dias_ate_processamento(spark):
    df = criar_df_transform(
        spark,
        [
            ("CC", "CREDITO", "PIX_RECEBIDO", "X", False, Decimal("1.00"),
             datetime(2026, 9, 20, 0, tzinfo=timezone.utc), date(2026, 10, 20)),
            ("CC", "CREDITO", "PIX_RECEBIDO", "X", False, Decimal("1.00"),
             datetime(2026, 10, 20, 23, 59, tzinfo=timezone.utc), date(2026, 10, 20)),
        ],
    )

    resultado = [r.dias_ate_processamento for r in SotTransform(spark).transform(df, DT_LOAD_SOT, ID_EXECUCAO).orderBy("dt_lancamento").collect()]

    assert resultado == [30, 0]

def test_transform_auditoria(spark):
    df = criar_df_transform(
        spark,
        [
            ("CC", "CREDITO", "PIX_RECEBIDO", "X", False, Decimal("1.00"),
             datetime(2026, 10, 20, 12, tzinfo=timezone.utc), date(2026, 10, 20)),
        ],
    )

    linha = SotTransform(spark).transform(df, DT_LOAD_SOT, ID_EXECUCAO).first()

    assert linha.id_execucao == ID_EXECUCAO
    # O collect() devolve o horário no fuso da máquina; convertendo para UTC,
    # a comparação funciona em qualquer computador.
    assert linha.dt_load_sot.astimezone(timezone.utc) == DT_LOAD_SOT


def registro_bronze(**alteracoes):
    """Registro como os gravados na Bronze; aceita colunas alteradas ou extras."""
    registro = {
        "id_transacao": "t-1",
        "id_contrato": "c-1",
        "id_conta": "0003",
        "cnpj": "0L8KQFJRQH9QW",
        "cod_agencia": "0001",
        "tipo_contrato": "CC",
        "tipo_lancamento": "CREDITO",
        "tipo_produto": "PIX_RECEBIDO",
        "valor_lancamento": Decimal("10.00"),
        "dt_lancamento": datetime(2026, 10, 20, 12, tzinfo=timezone.utc),
        "dt_processamento": date(2026, 10, 20),
        "cod_cosif": "COSIF-MOCK-001",
        "flag_estorno": False,
        "id_lote": "l-1",
    }
    registro.update(alteracoes)
    return registro


def test_aplicar_schema_define_colunas_e_tipos(spark):
    silver = SotTransform(spark)
    df = spark.createDataFrame([registro_bronze(valor_lancamento=10.5, coluna_extra="x")])

    resultado = silver.aplicar_schema(df)

    assert resultado.columns == list(silver.SCHEMA_SILVER)
    assert {c.name: c.dataType for c in resultado.schema} == silver.SCHEMA_SILVER
    assert resultado.first()["valor_lancamento"] == Decimal("10.50")


def test_aplicar_schema_falha_sem_coluna(spark):
    registro = registro_bronze()
    del registro["tipo_produto"]
    df = spark.createDataFrame([registro])

    with pytest.raises(ValueError, match="tipo_produto"):
        SotTransform(spark).aplicar_schema(df)


def test_separar_lancamento_invalido(spark):
    df = spark.createDataFrame([
        registro_bronze(id_transacao="t-1", tipo_lancamento="CREDITO"),
        registro_bronze(id_transacao="t-2", tipo_lancamento=" debito"),
        registro_bronze(id_transacao="t-3", tipo_lancamento="TARIFA"),
    ])

    validos, rejeitados = SotTransform(spark).separar_lancamento_invalido(df)

    assert {r.id_transacao for r in validos.collect()} == {"t-1", "t-2"}
    assert [(r.id_transacao, r.motivo_rejeicao) for r in rejeitados.collect()] == [
        ("t-3", "tipo_lancamento inválido: TARIFA")
    ]


def test_transform_padroniza_tipo_produto(spark):
    df = SotTransform(spark).aplicar_schema(
        spark.createDataFrame([registro_bronze(tipo_produto=" pix_recebido ")])
    )

    linha = SotTransform(spark).transform(df, DT_LOAD_SOT, ID_EXECUCAO).first()

    assert linha.tipo_produto == "PIX_RECEBIDO"


def test_rejeitados_recebem_auditoria(spark):
    df = spark.createDataFrame([registro_bronze(tipo_lancamento="IOF")])
    _, rejeitados = SotTransform(spark).separar_lancamento_invalido(df)

    linha = SotTransform(spark).adicionar_auditoria(rejeitados, DT_LOAD_SOT, ID_EXECUCAO).first()

    assert linha.id_execucao == ID_EXECUCAO
    assert linha.dt_load_sot.astimezone(timezone.utc) == DT_LOAD_SOT


def test_ordenar_como_tabela_segue_a_tabela_e_poe_colunas_novas_no_fim(spark):
    """A ordem que causou o erro na Bronze: cnpj/cod_agencia trocados e coluna nova no meio."""
    df = spark.createDataFrame(
        [("t-1", "0001", "CNPJ", "CREDITO", "PIX_RECEBIDO")],
        "id_transacao string, cod_agencia string, cnpj string, tipo_lancamento string, tipo_produto string",
    )

    resultado = SotTransform.ordenar_como_tabela(df, ["id_transacao", "cnpj", "cod_agencia", "tipo_lancamento"])

    assert resultado.columns == ["id_transacao", "cnpj", "cod_agencia", "tipo_lancamento", "tipo_produto"]
    assert resultado.first()["cnpj"] == "CNPJ"


def test_regras_data_quality_contem_as_regras(spark):
    silver = SotTransform(spark)

    ruleset = silver.regras_data_quality()

    assert ruleset.startswith("Rules = [") and ruleset.endswith("]")
    assert 'IsUnique "id_transacao"' in ruleset
    assert 'ColumnValues "valor_lancamento" > 0' in ruleset
    for coluna in silver.SCHEMA_SILVER:
        assert f'IsComplete "{coluna}"' in ruleset
    assert ruleset.count("CustomSql") == 2


def contar_violacoes(spark, silver, nome, registros):
    """Executa a consulta CustomSql como o Glue Data Quality, com a tabela `primary`."""
    silver.aplicar_schema(spark.createDataFrame(registros)).createOrReplaceTempView("primary")
    return spark.sql(silver.consultas_data_quality()[nome]).first()[0]


def test_custom_sql_lancamento_apos_processamento(spark):
    silver = SotTransform(spark)
    registros = [
        registro_bronze(id_transacao="mesmo-dia", dt_lancamento=datetime(2026, 10, 20, 23, 59, tzinfo=timezone.utc)),
        registro_bronze(id_transacao="antes", dt_lancamento=datetime(2026, 10, 1, tzinfo=timezone.utc)),
        registro_bronze(id_transacao="depois", dt_lancamento=datetime(2026, 10, 21, 0, 1, tzinfo=timezone.utc)),
    ]

    assert contar_violacoes(spark, silver, "lancamento_apos_processamento", registros) == 1


def test_custom_sql_texto_vazio(spark):
    silver = SotTransform(spark)
    registros = [
        registro_bronze(id_transacao="ok"),
        registro_bronze(id_transacao="vazio", cnpj=""),
        registro_bronze(id_transacao="espacos", tipo_produto="   "),
    ]

    assert contar_violacoes(spark, silver, "texto_vazio", registros) == 2
