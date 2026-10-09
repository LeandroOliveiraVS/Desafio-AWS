from faker import Faker
import json
import os
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

class DataCreator:
    def __init__(self, data_processamento, quantidade_contas: int = 100):
        self.fake = Faker("pt_BR")
        self.data_processamento = data_processamento
        self.quantidade_contas = quantidade_contas
        self.contas = self._criar_contas_e_contratos(quantidade_contas)

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

    def _criar_contas_e_contratos(self, quantidade_contas: int) -> list[dict]:

        # Seleção sem repetição: IDs únicos nesta execução do gerador.
        numeros_conta = random.sample(range(100_000_000), quantidade_contas)

        contas = []

        for numero in numeros_conta:
            id_conta = f"{numero:08d}"
            cod_agencia = str(self.fake.random_number(digits=4, fix_len=True))

            contratos = [{
                'id_contrato': str(uuid.uuid4()),
                'tipo_contrato': random.choice(self._TIPOS_CONTRATO),
            } for _ in range(random.randint(3, 5))]  # Cada conta terá entre 3 e 5 contratos.

            contas.append({
                'id_conta': id_conta,
                'cod_agencia': cod_agencia,
                'contratos': contratos
            })
            