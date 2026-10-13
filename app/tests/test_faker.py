from datetime import date

from app.src.data_generator.data_faker import DataCreator

def test_gerar_registros():
    gerador = DataCreator(date(2025, 2, 10), quantidade_contas=10)

    registros = gerador.gerar_registros(5)

    assert len(registros) == 5

def test_id_transacao_e_unico_no_lote():
    gerador = DataCreator(date(2025, 2, 10), quantidade_contas=10)

    registros = gerador.gerar_registros(20)
    ids = [registro["id_transacao"] for registro in registros]

    assert len(ids) == len(set(ids))


def test_valor_lancamento_e_positivo():
    gerador = DataCreator(date(2025, 2, 10), quantidade_contas=10)

    registros = gerador.gerar_registros(20)

    assert all(registro["valor_lancamento"] > 0 for registro in registros)

def test_gerar_cnpjs_unicos():
    gerador = DataCreator(
        data_processamento=date(2025, 2, 10),
        quantidade_contas=5,
    )

    cnpjs = [
        gerador.gerar_cnpj_unico()
        for _ in range(100)
    ]

    assert len(cnpjs) == len(set(cnpjs))