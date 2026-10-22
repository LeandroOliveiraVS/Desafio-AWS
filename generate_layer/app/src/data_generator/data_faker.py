from faker import Faker
import string
import os
from pathlib import Path
import csv
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

class DataCreator:
    """
    Classe responsável por gerar dados fictícios para simular transações bancárias.

    Args:
        data_processamento (datetime): Data de processamento das transações.
        quantidade (int, opcional): Quantidade de registros a serem gerados. Padrão é 1000.

    Attributes:
        fake (Faker): Instância do Faker para gerar dados fictícios.
        data_processamento (datetime): Data de processamento das transações.
        quantidade (int): Quantidade de registros a serem gerados.
        _contas (list[dict]): Lista de contas fictícias com contratos associados.

    Methods:
        carregar_contas_csv(): Lê os arquivos CSV de contas e contratos e retorna uma lista de contas fictícias.
        gerar_registro(): Gera um registro fictício de transação bancária.
        gerar_registros(): Gera uma lista de registros fictícios de transações bancárias.

    """
    def __init__(self, data_processamento, quantidade: int = 1000):
        
        self.fake = Faker("pt_BR")
        self.data_processamento = data_processamento
        self.quantidade = quantidade
        self._id_lote = str(uuid.uuid4())

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

        self.contas = self._carregar_contas_csv()

    def _carregar_contas_csv(self) -> list[dict]:
        """
        Lê o CSV de contas e contratos localizados na mesma pasta do handler.py.

        Returns:
            Lista de contas fictícias com contratos associados.
            
        Raises:
            ValueError: Se o CSV não contiver os campos obrigatórios ou estiver vazio.

        Example:
            [
                {
                    "identificadores": [
                        ("id_conta_1", "cod_agencia_1", "cnpj_1"),
                        ("id_conta_2", "cod_agencia_2", "cnpj_2"),
                        ...
                    ],
                    "contratos_por_conta": {
                        "id_conta_1": [
                            {"id_contrato": "id_contrato_1", "tipo_contrato": "tipo_contrato_1"},
                            {"id_contrato": "id_contrato_2", "tipo_contrato": "tipo_contrato_2"},
                        ],
                        "id_conta_2": [
                            {"id_contrato": "id_contrato_3", "tipo_contrato": "tipo_contrato_3"},
                        ],
                    }
                }
            ]
        """
        contas = []

        pasta_atual = Path(__file__).resolve().parent
        caminho_contas = pasta_atual / "contas.csv"
        caminho_contratos = pasta_atual / "contratos.csv"

        if not caminho_contas.exists():
            raise FileNotFoundError(
                f"Arquivo não encontrado: {caminho_contas}"
            )

        if not caminho_contratos.exists():
            raise FileNotFoundError(
                f"Arquivo não encontrado: {caminho_contratos}"
            )

        with open(caminho_contas, 'r', newline='', encoding='utf-8-sig') as arquivo_contas:
            leitor = csv.DictReader(arquivo_contas)

            if not leitor.fieldnames:
                raise ValueError("O CSV não contém cabeçalho.")

            leitor.fieldnames = [campo.strip() for campo in leitor.fieldnames]
            campos_obrigatorios = {"id_conta", "cod_agencia", "cnpj"}

            if not campos_obrigatorios.issubset(leitor.fieldnames):
                raise ValueError(
                    "O CSV deve conter as colunas "
                    "id_conta, cod_agencia e cnpj."
                )

            identificadores = []

            for numero_linha, linha in enumerate(leitor, start=2):
                id_conta = (linha.get("id_conta") or "").strip()
                cod_agencia = (linha.get("cod_agencia") or "").strip()
                cnpj = (linha.get("cnpj") or "").strip()

                if not id_conta or not cod_agencia or not cnpj:
                    raise ValueError(
                        f"Campo vazio no CSV, linha {numero_linha}."
                    )

                identificadores.append((id_conta, cod_agencia, cnpj))
        # Contratos
        with open(caminho_contratos, 'r', newline='', encoding='utf-8-sig') as arquivo_contratos:
            leitor_contratos = csv.DictReader(arquivo_contratos)
            contratos_por_conta = {}

            for linha in leitor_contratos:
                id_conta = (linha.get("id_conta") or "").strip()
                id_contrato = (linha.get("id_contrato") or "").strip()
                tipo_contrato = (linha.get("tipo_contrato") or "").strip()

                if not id_conta or not id_contrato or not tipo_contrato:
                    raise ValueError(
                        f"Campo vazio no CSV de contratos, linha {leitor_contratos.line_num}."
                    )

                if id_conta not in contratos_por_conta:
                    contratos_por_conta[id_conta] = []

                contratos_por_conta[id_conta].append({
                    "id_contrato": id_contrato,
                    "tipo_contrato": tipo_contrato,
                })

        if not identificadores:
            raise ValueError("O CSV de identificadores não contém registros.")
        if not contratos_por_conta:
            raise ValueError("O CSV de contratos não contém registros.")

        contas.append({
            "identificadores": identificadores,
            "contratos": contratos_por_conta,
        })

        return contas

    def gerar_registro(self) -> dict:
        """
        Gera um registro fictício de transação bancária.

        Returns:
            dict: Registro de transação com dados fictícios.
        """
        conta = random.choice(self.contas)

        # Seleciona apenas contas que possuem ao menos um contrato associado
        identificadores_com_contrato = [
            identificador
            for identificador in conta["identificadores"]
            if identificador[0] in conta["contratos"]
        ]

        if not identificadores_com_contrato:
            raise ValueError("Nenhuma conta possui contrato associado.")

        id_conta, cod_agencia, cnpj = random.choice(identificadores_com_contrato)

        # Obtém a lista de contratos daquela conta específica
        contrato = random.choice(conta["contratos"][id_conta])

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
            'id_conta': id_conta,
            'cod_agencia': cod_agencia,
            'cnpj': cnpj,
            'tipo_contrato': contrato["tipo_contrato"],
            'tipo_lancamento': random.choice(self._TIPOS_LANCAMENTO),
            'valor_lancamento': Decimal(str(round(random.uniform(0.01, 10000.00), 2))),
            'dt_lancamento': dt_lancamento,
            'dt_processamento': self.data_processamento,
            'cod_cosif': cod_cosif,
            'flag_estorno': self.fake.boolean(chance_of_getting_true=5),
            'id_lote': self._id_lote
        }
    
    def gerar_registros(self) -> list[dict]:
        """
        Gera uma lista de registros fictícios de transações bancárias.

        Args:
            quantidade (int): Quantidade de registros a serem gerados.

        Returns:
            list[dict]: Lista de registros de transação com dados fictícios.
        """

        return [
            self.gerar_registro
            for _ in range(self.quantidade)
        ]
