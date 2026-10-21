"""
Business views da camada Gold.

Cada arquivo deste pacote define uma única business view: uma classe que herda
`SpecTransform` e implementa `create_business_view`. O nome do arquivo é o valor
do parâmetro `--business_view` do job e também o nome da tabela Gold.

Exemplo (`business_views/resumo_diario.py`):

    from pyspark.sql import DataFrame, functions as F

    from spec_transform import SpecTransform


    class ResumoDiario(SpecTransform):
        def create_business_view(self, df: DataFrame) -> DataFrame:
            return df.groupBy("dt_processamento", "tipo_contrato").agg(
                F.sum("valor_lancamento").alias("valor_total")
            )
"""
