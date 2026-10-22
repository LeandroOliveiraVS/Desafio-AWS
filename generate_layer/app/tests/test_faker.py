import random
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


def test_sem_taxa_de_erros_nao_ha_nulos_nem_duplicatas():
    gerador = data_faker_module.DataCreator(date(2025, 2, 10), quantidade=50)

    registros = gerador.gerar_registros()
    ids = [registro["id_transacao"] for registro in registros]

    assert None not in ids
    assert len(ids) == len(set(ids))
    assert gerador.erros_injetados == {"chave_nula": 0, "duplicado": 0}


def test_taxa_de_erros_total_injeta_nulos_e_duplicatas():
    random.seed(42)
    gerador = data_faker_module.DataCreator(date(2025, 2, 10), quantidade=200, taxa_erros=1.0)

    registros = gerador.gerar_registros()

    # A quantidade não muda: os erros substituem registros, não acrescentam.
    assert len(registros) == 200
    assert sum(gerador.erros_injetados.values()) == 200

    com_chave_nula = [
        r for r in registros
        if None in (r["id_transacao"], r["id_conta"], r["id_contrato"])
    ]
    ids_preenchidos = [r["id_transacao"] for r in registros if r["id_transacao"] is not None]
    duplicatas = len(ids_preenchidos) - len(set(ids_preenchidos))

    assert len(com_chave_nula) > 0
    assert duplicatas > 0


def test_primeiro_registro_com_erro_e_chave_nula():
    """O primeiro registro não tem registro anterior para duplicar."""
    gerador = data_faker_module.DataCreator(date(2025, 2, 10), quantidade=1, taxa_erros=1.0)

    gerador.gerar_registros()

    assert gerador.erros_injetados == {"chave_nula": 1, "duplicado": 0}


@pytest.mark.parametrize("taxa", [-0.1, 1.5])
def test_taxa_de_erros_invalida(taxa):
    with pytest.raises(ValueError, match="taxa de erros"):
        data_faker_module.DataCreator(date(2025, 2, 10), quantidade=1, taxa_erros=taxa)
