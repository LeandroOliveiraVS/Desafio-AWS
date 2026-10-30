import sys
import textwrap

import pytest
from pyspark.sql import DataFrame

from spec_transform import SpecTransform, carregar_business_view


class ViewSemParticao(SpecTransform):
    COLUNAS_PARTICAO = ()

    def create_business_view(self, df: DataFrame) -> DataFrame:
        return df


class ViewParticionada(SpecTransform):
    def create_business_view(self, df: DataFrame) -> DataFrame:
        return df.select("id_transacao")


@pytest.fixture
def pacote_views(tmp_path, monkeypatch):
    """Cria um pacote temporário de business views e o coloca no sys.path."""
    pacote = tmp_path / "views_teste"
    pacote.mkdir()
    (pacote / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))

    def criar_view(nome: str, codigo: str) -> None:
        (pacote / f"{nome}.py").write_text(textwrap.dedent(codigo))

    yield criar_view

    for modulo in [m for m in sys.modules if m.startswith("views_teste")]:
        del sys.modules[modulo]


def test_classe_base_nao_pode_ser_instanciada(spark):
    with pytest.raises(TypeError):
        SpecTransform(spark)


def test_view_sem_create_business_view_nao_pode_ser_instanciada(spark):
    class ViewIncompleta(SpecTransform):
        pass

    with pytest.raises(TypeError, match="create_business_view"):
        ViewIncompleta(spark)


def test_particao_padrao_e_dt_processamento():
    assert ViewParticionada.COLUNAS_PARTICAO == ("dt_processamento",)


def test_gravar_falha_sem_coluna_de_particao(spark):
    view = ViewParticionada(spark)
    df = view.create_business_view(
        spark.createDataFrame([("t-1", "2026-10-20")], ["id_transacao", "dt_processamento"])
    )

    with pytest.raises(ValueError, match="dt_processamento"):
        view.gravar_tabela_iceberg(df, "glue_catalog.gold.teste", "2")


def test_ordenar_como_tabela_segue_a_tabela_e_poe_colunas_novas_no_fim(spark):
    df = spark.createDataFrame([("c-1", "10.00", "5.00", "2026-10-01")], ["id_contrato", "saldo_mes", "saldo", "data_saldo"])

    resultado = SpecTransform.ordenar_como_tabela(df, ["data_saldo", "id_contrato", "saldo"])

    assert resultado.columns == ["data_saldo", "id_contrato", "saldo", "saldo_mes"]
    assert resultado.first()["saldo"] == "5.00"


def test_carregar_business_view(spark, pacote_views):
    pacote_views(
        "resumo",
        """
        from spec_transform import SpecTransform

        class Resumo(SpecTransform):
            def create_business_view(self, df):
                return df.limit(1)
        """,
    )

    view = carregar_business_view("resumo", spark, pacote="views_teste")

    assert type(view).__name__ == "Resumo"
    assert view.spark is spark
    assert view.create_business_view(spark.range(3)).count() == 1


def test_carregar_business_view_inexistente(spark, pacote_views):
    with pytest.raises(ValueError, match="não encontrada"):
        carregar_business_view("nao_existe", spark, pacote="views_teste")


def test_carregar_business_view_nome_invalido(spark):
    with pytest.raises(ValueError, match="inválido"):
        carregar_business_view("x; DROP TABLE", spark)


def test_carregar_business_view_sem_classe(spark, pacote_views):
    pacote_views("vazia", "VALOR = 1\n")

    with pytest.raises(ValueError, match="exatamente uma"):
        carregar_business_view("vazia", spark, pacote="views_teste")


def test_carregar_business_view_com_duas_classes(spark, pacote_views):
    pacote_views(
        "duplicada",
        """
        from spec_transform import SpecTransform

        class A(SpecTransform):
            def create_business_view(self, df):
                return df

        class B(SpecTransform):
            def create_business_view(self, df):
                return df
        """,
    )

    with pytest.raises(ValueError, match="exatamente uma"):
        carregar_business_view("duplicada", spark, pacote="views_teste")
