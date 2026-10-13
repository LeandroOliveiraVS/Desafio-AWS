from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO

import polars as pl
import pytest

from app.src.data_generator import handler as handler_module


class FakeS3:
    """Cliente S3 falso que guarda os argumentos de put_object."""

    def __init__(self):
        self.chamadas = []

    def put_object(self, **kwargs):
        self.chamadas.append(kwargs)


def criar_registro_teste(data_processamento):
    """Cria um registro mínimo para testar a serialização Parquet."""
    return {
        "id_transacao": "transacao-teste-001",
        "id_contrato": "contrato-teste-001",
        "id_conta": "00001234",
        "cnpj": "12345678901234",
        "cod_agencia": "0123",
        "tipo_contrato": "CC",
        "tipo_lancamento": "CREDITO",
        "valor_lancamento": Decimal("125.50"),
        "dt_lancamento": datetime(
            2025, 2, 10, 14, 15, tzinfo=timezone.utc
        ),
        "dt_processamento": data_processamento,
        "cod_cosif": None,
        "flag_estorno": False,
        "id_lote": "lote-teste-001",
    }


def configurar_handler(monkeypatch):
    """Configura variáveis e substitui o cliente S3 por um falso."""
    monkeypatch.setenv("BUCKET_DESTINO", "bucket-teste")
    monkeypatch.setenv("PREFIXO_DESTINO", "contratos")

    s3_falso = FakeS3()
    monkeypatch.setattr(
        handler_module.boto3,
        "client",
        lambda nome_servico: s3_falso,
    )

    return s3_falso

def test_obter_data_hora_particao_converte_para_utc():
    """Verifica que uma data com fuso horário é convertida para UTC."""
    resultado = handler_module.LambdaHandler._obter_data_hora_particao({
        "data_particao": "2025-02-10T14:30:00-03:00",
    })

    assert resultado == datetime(
        2025, 2, 10, 17, 30, tzinfo=timezone.utc
    )

def test_criar_parquet():
    """Verifica que os registros são serializados em um Parquet válido."""
    registro = criar_registro_teste(date(2025, 2, 10))

    conteudo = handler_module.LambdaHandler._criar_parquet([registro])
    dataframe = pl.read_parquet(BytesIO(conteudo))

    assert dataframe.height == 1
    assert "cnpj" in dataframe.columns
    assert dataframe["id_transacao"][0] == "transacao-teste-001"
    assert dataframe["valor_lancamento"][0] == Decimal("125.50")
    assert dataframe["dt_processamento"][0] == date(2025, 2, 10)


def test_executar_grava_parquet_no_s3_com_particao(monkeypatch):
    """Verifica que a função LambdaHandler executa corretamente e grava no S3."""
    s3_falso = configurar_handler(monkeypatch)

    class DataCreatorFalso:
        """Gerador falso para tornar o teste previsível."""

        def __init__(self, data_processamento):
            self.data_processamento = data_processamento

        def gerar_registros(self, quantidade):
            return [
                criar_registro_teste(self.data_processamento)
                for _ in range(quantidade)
            ]

    monkeypatch.setattr(
        handler_module,
        "DataCreator",
        DataCreatorFalso,
    )

    resultado = handler_module.LambdaHandler().executar({
        "quantidade": 1,
        "data_particao": "2025-02-10T14:30:00Z",
    })

    assert resultado["statusCode"] == 200
    assert resultado["bucket"] == "bucket-teste"
    assert resultado["formato"] == "parquet"
    assert resultado["quantidade"] == 1

    assert len(s3_falso.chamadas) == 1
    chamada = s3_falso.chamadas[0]

    assert chamada["Bucket"] == "bucket-teste"
    assert chamada["Key"].startswith(
        "contratos/2025/02/10/14/part-"
    )
    assert chamada["Key"].endswith(".parquet")

    dataframe = pl.read_parquet(BytesIO(chamada["Body"]))

    assert dataframe.height == 1
    assert "id_transacao" in dataframe.columns
    assert dataframe["id_transacao"][0] == "transacao-teste-001"


def test_executar_rejeita_quantidade_zero(monkeypatch):
    """Verifica que a função LambdaHandler rejeita quantidade de registros <= 0."""
    s3_falso = configurar_handler(monkeypatch)
    handler = handler_module.LambdaHandler()

    with pytest.raises(ValueError, match="quantidade"):
        handler.executar({"quantidade": 0})

    assert s3_falso.chamadas == []
