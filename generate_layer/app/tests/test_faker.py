from datetime import date
import pytest
import generate_layer.app.src.data_generator.data_faker as data_faker_module

@pytest.fixture
def data_creator_e_pasta_temporaria(tmp_path, monkeypatch):
    """Redireciona a leitura dos CSVs para uma pasta temporária."""
    arquivo_modulo = tmp_path / "data_faker.py"

    monkeypatch.setattr(
        data_faker_module,
        "__file__",
        str(arquivo_modulo),
    )

    # O método testado não usa os atributos inicializados por __init__.
    data_creator = data_faker_module.DataCreator.__new__(
        data_faker_module.DataCreator
    )

    return data_creator, tmp_path

def test_carregar_contas_csv_le_identificadores_e_contratos(data_creator_e_pasta_temporaria):
    """
    Testa se o método _carregar_contas_csv lê corretamente os identificadores e contratos dos arquivos CSV.
    """
    data_creator, pasta = data_creator_e_pasta_temporaria

    (pasta / "contas.csv").write_text(
        "id_conta,cod_agencia,cnpj\n"
        "0001,0001,0ABC12345\n"
        "0002,0001,0XYZ67890\n",
        encoding="utf-8",
    )

    (pasta / "contratos.csv").write_text(
        "id_conta,id_contrato,tipo_contrato\n"
        "0001,contrato-001,CC\n"
        "0001,contrato-002,POUP\n"
        "0002,contrato-003,CDB\n",
        encoding="utf-8",
    )

    resultado = data_creator._carregar_contas_csv()

    assert resultado == [
        {
            "identificadores": [
                ("0001", "0001", "0ABC12345"),
                ("0002", "0001", "0XYZ67890"),
            ],
            "contratos": {
                "0001": [
                    {
                        "id_contrato": "contrato-001",
                        "tipo_contrato": "CC",
                    },
                    {
                        "id_contrato": "contrato-002",
                        "tipo_contrato": "POUP",
                    },
                ],
                "0002": [
                    {
                        "id_contrato": "contrato-003",
                        "tipo_contrato": "CDB",
                    }
                ],
            },
        }
    ]

"""def test_criar_contas():
    "Verifica que a criação de contas gera a quantidade correta de contas."
    gerador = data_faker_module.DataCreator(date(2025, 2, 10), quantidade_contas=10)

    assert len(gerador.contas) == 10
    assert all(len(gerador.contas[i]['id_conta']) == 6 for i in range(10)) # cada id_conta tem 6 dígitos
    assert all(len(gerador.contas[i]['cod_agencia']) == 4 for i in range(10)) # cada cod_agencia tem 4 dígitos
    assert all(len(gerador.contas[i]['contratos']) >= 3 and len(gerador.contas[i]['contratos']) <= 5 for i in range(10)) # cada conta tem entre 3 e 5 contratos
"""

def test_gerar_registros():
    gerador = data_faker_module.DataCreator(date(2025, 2, 10), quantidade=5)

    registros = gerador.gerar_registros()

    assert len(registros) == 5

def test_id_transacao_e_unico_no_lote():
    gerador = data_faker_module.DataCreator(date(2025, 2, 10), quantidade=20)

    registros = gerador.gerar_registros()
    ids = [registro["id_transacao"] for registro in registros]

    assert len(ids) == len(set(ids))


def test_valor_lancamento_e_positivo():
    gerador = data_faker_module.DataCreator(date(2025, 2, 10), quantidade=20)

    registros = gerador.gerar_registros()

    assert all(registro["valor_lancamento"] > 0 for registro in registros)

def test_gerar_registro_unico():
    gerador = data_faker_module.DataCreator(date(2025, 2, 10), quantidade=10)

    registro = gerador.gerar_registro()

    assert isinstance(registro, dict)
    assert "id_transacao" in registro
    assert "id_contrato" in registro
    assert "id_conta" in registro
    assert "cnpj" in registro
    assert "cod_agencia" in registro
    assert "tipo_contrato" in registro
    assert "tipo_lancamento" in registro
    assert "valor_lancamento" in registro
    assert "dt_lancamento" in registro
    assert "dt_processamento" in registro
    assert "cod_cosif" in registro
    assert "flag_estorno" in registro
    assert "id_lote" in registro
