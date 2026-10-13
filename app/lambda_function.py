from app.source.data_generator.handler import LambdaHandler

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