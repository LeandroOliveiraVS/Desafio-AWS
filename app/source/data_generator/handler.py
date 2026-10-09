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
        "id_transacao": pl.String,
        "id_contrato": pl.String,
        "id_conta": pl.String,
        "cod_agencia": pl.String,
        "tipo_contrato": pl.String,
        "tipo_lancamento": pl.String,
        "valor_lancamento": pl.Decimal(precision=18, scale=2),
        "dt_lancamento": pl.Datetime(
            time_unit="us",
            time_zone="UTC",
        ),
        "dt_processamento": pl.Date,
        "cod_cosif": pl.String,
        "flag_estorno": pl.Boolean,
        "id_lote": pl.String,
    }
    def __init__(self):
        self.s3 = boto3.client("s3")
        self.bucket = os.environ['BUCKET_DESTINO']
    
def lambda_handler(event, context):
    return LambdaHandler().executar(event or {})