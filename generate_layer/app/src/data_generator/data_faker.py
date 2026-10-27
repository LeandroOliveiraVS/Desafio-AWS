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
    def __init__(self, data_processamento, quantidade: int = 1000, taxa_erros: float = 0.0):

        if not 0 <= taxa_erros <= 1:
            raise ValueError("A taxa de erros deve estar entre 0 e 1.")

        self.fake = Faker("pt_BR")
        self.data_processamento = data_processamento
        self.quantidade = quantidade
        self._id_lote = str(uuid.uuid4())

        # Erros injetados de propósito para exercitar a quarentena da Silver.
        self.taxa_erros = taxa_erros
        self.erros_injetados = {"chave_nula": 0, "duplicado": 0}
        self._CAMPOS_ANULAVEIS = ["id_transacao", "id_conta", "id_contrato"]

        self._TIPOS_CONTRATO = [
            "CC",
            "POUP",
            "CDB",
            "LCI",
            "CONSORCIO",
            "SEGURO",
        ]

        # Peso (chance de sorteio) de cada tipo de lançamento e, dentro dele, peso
        # e faixa de valor de cada tipo de produto. Calibrados para que entradas
        # (CREDITO) e saídas (DEBITO) se equilibrem: em média um lançamento soma
        # cerca de +60, então os saldos ficam distribuídos em torno de zero, com
        # leve viés positivo.
        self._PERFIL_LANCAMENTO = {
            "CREDITO": {
                "peso": 40,
                "produtos": {
                    "PIX_RECEBIDO": {"peso": 55, "faixa": (10.00, 3000.00)},
                    "TED_RECEBIDA": {"peso": 15, "faixa": (100.00, 8000.00)},
                    "DEPOSITO": {"peso": 15, "faixa": (50.00, 2000.00)},
                    "SALARIO": {"peso": 10, "faixa": (1500.00, 8000.00)},
                    "RESGATE_INVESTIMENTO": {"peso": 5, "faixa": (100.00, 5000.00)},
                },
            },
            "DEBITO": {
                "peso": 60,
                "produtos": {
                    "PIX_ENVIADO": {"peso": 40, "faixa": (10.00, 3000.00)},
                    "COMPRA_DEBITO": {"peso": 28, "faixa": (5.00, 800.00)},
                    "PAGAMENTO_BOLETO": {"peso": 23, "faixa": (50.00, 5000.00)},
                    "SAQUE": {"peso": 9, "faixa": (20.00, 1500.00)},
                },
            },
        }
        self._TIPOS_LANCAMENTO = list(self._PERFIL_LANCAMENTO)

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

        tipo_lancamento = self._sortear_tipo_lancamento()
        tipo_produto = self._sortear_tipo_produto(tipo_lancamento)

        return {
            'id_transacao': str(uuid.uuid4()),
            'id_contrato': contrato["id_contrato"],
            'id_conta': id_conta,
            'cod_agencia': cod_agencia,
            'cnpj': cnpj,
            'tipo_contrato': contrato["tipo_contrato"],
            'tipo_lancamento': tipo_lancamento,
            'tipo_produto': tipo_produto,
            'valor_lancamento': self._sortear_valor(tipo_lancamento, tipo_produto),
            'dt_lancamento': dt_lancamento,
            'dt_processamento': self.data_processamento,
            'cod_cosif': cod_cosif,
            'flag_estorno': self.fake.boolean(chance_of_getting_true=5),
            'id_lote': self._id_lote
        }
    
    def _sortear_tipo_lancamento(self) -> str:
        """Sorteia o tipo de lançamento de acordo com os pesos de `_PERFIL_LANCAMENTO`."""
        pesos = [perfil["peso"] for perfil in self._PERFIL_LANCAMENTO.values()]
        return random.choices(self._TIPOS_LANCAMENTO, weights=pesos, k=1)[0]

    def _sortear_tipo_produto(self, tipo_lancamento: str) -> str:
        """Sorteia um tipo de produto do tipo de lançamento, de acordo com os pesos dos produtos."""
        produtos = self._PERFIL_LANCAMENTO[tipo_lancamento]["produtos"]
        pesos = [produto["peso"] for produto in produtos.values()]
        return random.choices(list(produtos), weights=pesos, k=1)[0]

    def _sortear_valor(self, tipo_lancamento: str, tipo_produto: str) -> Decimal:
        """Sorteia um valor positivo, com duas casas, dentro da faixa do tipo de produto."""
        produto = self._PERFIL_LANCAMENTO[tipo_lancamento]["produtos"][tipo_produto]
        minimo, maximo = produto["faixa"]
        return Decimal(str(round(random.uniform(minimo, maximo), 2)))

    def gerar_registros(self) -> list[dict]:
        """
        Gera uma lista de registros fictícios de transações bancárias.

        Args:
            quantidade (int): Quantidade de registros a serem gerados.

        Com `taxa_erros` > 0, parte dos registros é gerada com erro proposital
        (chave nula ou duplicata); a quantidade total de registros não muda.

        Returns:
            list[dict]: Lista de registros de transação com dados fictícios.
        """
        registros = []

        for _ in range(self.quantidade):
            registro = self.gerar_registro()
            if random.random() < self.taxa_erros:
                registro = self._injetar_erro(registro, registros)
            registros.append(registro)

        return registros

    def _injetar_erro(self, registro: dict, anteriores: list[dict]) -> dict:
        """
        Troca o registro por uma cópia de um registro anterior (duplicata) ou
        anula uma de suas chaves.

        Args:
            registro: Registro recém-gerado.
            anteriores: Registros já gerados no lote, usados para duplicar.

        Returns:
            dict: Registro com o erro aplicado.
        """
        # O primeiro registro do lote não tem o que duplicar.
        if anteriores and random.random() < 0.5:
            self.erros_injetados["duplicado"] += 1
            return dict(random.choice(anteriores))

        self.erros_injetados["chave_nula"] += 1
        return {**registro, random.choice(self._CAMPOS_ANULAVEIS): None}
