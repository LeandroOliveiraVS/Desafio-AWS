import sys
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

# No Glue, `spec_transform` e `business_views` ficam na raiz do zip do
# --extra-py-files; aqui a pasta src faz esse papel.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(scope="session")
def spark():
    """Sessão Spark local compartilhada pelos testes."""
    sessao = (
        SparkSession.builder.master("local[1]")
        .appName("testes-spec-transform")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield sessao
    sessao.stop()
