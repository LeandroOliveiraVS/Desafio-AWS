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
    """
    Classe responsável por lidar com eventos do AWS Lambda para gerar dados fictícios de transações bancárias e armazená-los em um bucket S3 no formato Parquet.

    As partições são organizadas por ano, mês, dia e hora em UTC.
    
    Attributes:
        s3 (boto3.client): Cliente S3 para interagir com o serviço S3 da AWS.
        bucket (str): Nome do bucket S3 onde os arquivos Parquet serão armazenados.
        prefixo (str): Prefixo do caminho no bucket S3 onde os arquivos Parquet serão armazenados.
    
    
    """
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
        """
        Obtém a data e a hora usadas no caminho da partição.

        Args:
            event: Evento da Lambda. Pode conter `data_particao` em formato ISO,
                como `2025-02-10T14:30:00Z`.

        Returns:
            Data e hora da partição convertidas para UTC.

        Raises:
            ValueError: Se `data_particao` não estiver em formato válido.
        """
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
        """
        Converte os registros para um arquivo Parquet usando Polars.

        Args:
            registros: Lista de registros gerados pelo `DataCreator`.

        Returns:
            Conteúdo do arquivo Parquet em bytes.
        """
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
        """
        Gera registros, cria o Parquet e o grava no S3.

        Args:
            event: Evento da Lambda. Campos aceitos:
                - `quantidade`: quantidade de registros a gerar; padrão 1000.
                - `quantidade_contas`: contas fictícias a criar; padrão 100.
                - `data_particao`: data/hora ISO opcional para a partição.

        Returns:
            Dicionário com o status da operação e a localização do arquivo no S3.

        Raises:
            ValueError: Se a quantidade de registros ou de contas não for positiva.
            Exception: Erros do gerador, do Polars ou do S3 são propagados.
        """
        quantidade = int(event.get("quantidade", 1000))

        if quantidade < 1:
            raise ValueError("A quantidade de registros deve ser maior que zero.")

        data_hora_particao = self._obter_data_hora_particao(event)
        data_processamento = data_hora_particao.date()

        logger.info(
            f"Criando Contas e contratos para a data de processamento: {data_processamento}, quantidade de registros: {quantidade}"
        )
        gerador = DataCreator(
            data_processamento= data_processamento
        )
        registros = gerador.gerar_registros(quantidade=quantidade)

        logger.info("Registros gerados; criando arquivo Parquet.")
        conteudo_parquet = self._criar_parquet(registros)

        chave = (
            f"{self.prefixo}/"
            f"{data_hora_particao:%Y}/"
            f"{data_hora_particao:%m}/"
            f"{data_hora_particao:%d}/"
            f"{data_hora_particao:%H}/"
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
    """
    Ponto de entrada da função AWS Lambda.

    Args:
        event: Evento recebido pela Lambda.
        context: Contexto de execução fornecido pelo runtime da Lambda.

    Returns:
        Resultado da execução de `LambdaHandler`.
    """
    return LambdaHandler().executar(event or {})