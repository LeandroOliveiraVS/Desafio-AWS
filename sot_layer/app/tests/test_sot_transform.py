from app.src.sot_transform import SotTransform

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