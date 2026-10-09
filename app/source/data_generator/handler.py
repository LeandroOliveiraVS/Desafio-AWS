import json
import logging
import os
import uuid
from datetime import date, datetime, timezone
from io import BytesIO

import boto3
import polars as pl

from app.source.data_generator.data_faker import DataCreator

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class LambdaHandler:
    SCHEMA = {
        "id_transacao": pl.Utf8,
        "id_contrato": pl.Utf8,
        "id_conta": pl.Utf8,
        "cod_agencia": pl.Utf8,
        "tipo_contrato": pl.Utf8,
        "tipo_lancamento": pl.Utf8,
        "valor_lancamento": pl.Decimal(precision=18, scale=2),
        "dt_lancamento": pl.Datetime(
            time_unit="us",
            time_zone="UTC",
        ),
        "dt_processamento": pl.Date,
        "cod_cosif": pl.Utf8,
        "flag_estorno": pl.Boolean,
        "id_lote": pl.Utf8,
    }
    def __init__(self):
        self.s3 = boto3.client("s3")
        self.bucket = os.environ['BUCKET_DESTINO']
        self.prefixo = os.environ['PREFIXO_DESTINO'].strip('/')

    @staticmethod
    def _obter_data_hora_particao(event: dict) -> datetime:

        valor = event.get("data_particao")
        if not valor:
            logger.warning("Nenhuma data de partição fornecida. Usando a data e hora atual.")
            return datetime.now(timezone.utc)

        # Aceita valores como "2025-02-10T14:30:00Z".
        valor = valor.replace("Z", "+00:00")
        data_hora = datetime.fromisoformat(valor)

        if data_hora.tzinfo is None:
            data_hora = data_hora.replace(tzinfo=timezone.utc)

        return data_hora.astimezone(timezone.utc)

    @classmethod
    def _criar_parquet(cls, registros: list[dict]) -> bytes:

        dataframe = pl.DataFrame(
            registros, 
            schema_overrides=cls.SCHEMA
        )

        buffer = BytesIO()
        dataframe.write_parquet(
            buffer, 
            compression="zstd"
        )

        buffer.seek(0)

        return buffer.getvalue()

    def executar(self, event: dict) -> dict:
        quantidade = int(event.get("quantidade", 1000))

        if quantidade < 1:
            raise ValueError("A quantidade de registros deve ser maior que zero.")

        data_hora_particao = self._obter_data_hora_particao(event)
        data_processamento = data_hora_particao.date()

        logger.info(
            f"Criando Contras e contratos para a data de processamento: {data_processamento}, quantidade de registros: {quantidade}"
        )
        gerador = DataCreator(
            data_processamento= data_processamento
        )

        registros = gerador.gerar_registros(quantidade=quantidade)
        conteudo_parquet = self._criar_parquet(registros)

        chave = (
            f"{self.prefixo}/"
            f"ANO/{data_hora_particao:%Y}/"
            f"MES/{data_hora_particao:%m}/"
            f"DIA/{data_hora_particao:%d}/"
            f"HORA/{data_hora_particao:%H}/"
            f"part-{uuid.uuid4()}.parquet"
        )

        self.s3.put_object(
            Bucket=self.bucket,
            Key=chave,
            Body=conteudo_parquet,
            ContentType="application/octet-stream",
        )

        logger.info(
            "Arquivo Parquet gravado em s3://%s/%s",
            self.bucket,
            chave,
        )

        return {
            "statusCode": 200,
            "quantidade": quantidade,
            "bucket": self.bucket,
            "chave": chave,
            "formato": "parquet",
        }

def lambda_handler(event, context):
    return LambdaHandler().executar(event or {})