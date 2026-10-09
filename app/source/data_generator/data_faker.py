from faker import Faker
import json
import os
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

class DataCreator:
    """
    Classe responsável por gerar dados fictícios para simular transações bancárias.

    Args:
        data_processamento (datetime): Data de processamento das transações.
        quantidade_contas (int, opcional): Quantidade de contas a serem geradas. Padrão é 100.
    """
    def __init__(self, data_processamento, quantidade_contas: int = 100):
        self.fake = Faker("pt_BR")
        self.data_processamento = data_processamento
        self.quantidade_contas = quantidade_contas

        self._TIPOS_CONTRATO = [
            "CC",
            "POUP",
            "CDB",
            "LCI",
            "CONSORCIO",
            "SEGURO",
        ]

        self._TIPOS_LANCAMENTO = [
            "DEBITO",
            "CREDITO",
            "TARIFA",
            "JUROS",
            "IOF",
        ]

        # Códigos fictícios para a demonstração.
        # Não são códigos COSIF oficiais.
        self._COSIF_MOCK = {
            "CC": "COSIF-MOCK-001",
            "POUP": "COSIF-MOCK-002",
            "CDB": "COSIF-MOCK-003",
            "LCI": "COSIF-MOCK-004",
            "CONSORCIO": "COSIF-MOCK-005",
            "SEGURO": "COSIF-MOCK-006",
        }

        self.contas = self._criar_contas(quantidade_contas)

    def _criar_contas(self, quantidade: int = 100) -> list[dict]:
        """
        Cria uma lista de contas fictícias com contratos associados.

        Args:
            quantidade (int): Quantidade de contas a serem geradas.

        Returns:
            list[dict]: Lista de contas com contratos.
        """
        
        # random.sample não repete números dentro desta execução.
        numeros_conta = random.sample(range(100_000_000), quantidade)
        contas = []

        for numero in numeros_conta:
            contratos = [
                {
                    "id_contrato": str(uuid.uuid4()),
                    "tipo_contrato": random.choice(self._TIPOS_CONTRATO),
                }
                for _ in range(random.randint(3, 5))
            ]

            contas.append({
                "id_conta": f"{numero:08d}",
                "cod_agencia": str(
                    self.fake.random_number(digits=4, fix_len=True)
                ),
                "contratos": contratos,
            })

        return contas

    def gerar_registro(self) -> dict:
        """
        Gera um registro fictício de transação bancária.

        Returns:
            dict: Registro de transação com dados fictícios.
        """
        conta = random.choice(self.contas)
        contrato = random.choice(conta["contratos"])

        data_inicio = datetime.combine(
            self.data_processamento - timedelta(days=30), time.min, tzinfo=timezone.utc
        )
        data_fim = datetime.combine(
            self.data_processamento, time.max, tzinfo=timezone.utc
        )

        dt_lancamento = self.fake.date_time_between(
            start_date=data_inicio, end_date=data_fim, tzinfo=timezone.utc
        )

        cod_cosif = self._COSIF_MOCK.get(contrato["tipo_contrato"], "COSIF-MOCK-000")

        return {
            'id_transacao': str(uuid.uuid4()),
            'id_contrato': contrato["id_contrato"],
            'id_conta': conta["id_conta"],
            'cod_agencia': conta["cod_agencia"],
            'tipo_contrato': contrato["tipo_contrato"],
            'tipo_lancamento': random.choice(self._TIPOS_LANCAMENTO),
            'valor_lancamento': Decimal(str(round(random.uniform(0.01, 10000.00), 2))),
            'dt_lancamento': dt_lancamento,
            'dt_processamento': self.data_processamento,
            'cod_cosif': cod_cosif,
            'flag_estorno': self.fake.boolean(chance_of_getting_true=5),
            'id_lote': str(uuid.uuid4()),
        }
    
    def gerar_registros(self, quantidade: int) -> list[dict]:
        """
        Gera uma lista de registros fictícios de transações bancárias.

        Args:
            quantidade (int): Quantidade de registros a serem gerados.

        Returns:
            list[dict]: Lista de registros de transação com dados fictícios.
        """
        return [
            self.gerar_registro()
            for _ in range(quantidade)
        ]
