# Projeto Desafio AWS- Engenharia de dados

## Visão geral
Este projeto está sendo desenvolvido como solução para um desafio de engenharia de dados.

## Estrutura
```
.
├── app/
│   ├── src/
│   │   └── data_generator/
│   │       ├── data_faker.py
│   │       └── handler.py
│   ├── tests/
│   │   ├── test_handler.py
│   │   └── test_data_faker.py
│   └── lambda_function.py
├── infra/
├── requirements.txt
├── .gitignore
├── .env
└── README.md
```

## Geração de dados fictícios
A Lambda funciona como etapa de simulação da origem dos dados:

- `DataCreator` lê os identificadores das contas e associa contratos fictícios.
- `LambdaHandler` gera os registros, cria um arquivo Parquet usando Polars e grava o resultado no S3.
- Os identificadores da conta: `id_conta`, `cod_agencia` e `cnpj` são lidos do CSV `identificadores` e armazenados como strings para preservar zeros à esquerda.
- Os identificadores dos contratos: `id_contrato` e `tipo_contrato` são lidos do CSV `contratos` utilizando o `id_conta`
- Os demais dados da transação, valores e datas, são gerados para fins de teste.

#### `identificadores.csv`

Contém os identificadores das contas:

```csv
id_conta,cod_agencia,cnpj
0001,0001,000000001
0002,0001,000000002
```

#### `contratos.csv`

Contém os contratos associados a cada conta:

```csv
id_conta,id_contrato,tipo_contrato
0001,contrato-0001-01,CC
0001,contrato-0001-02,POUP
0001,contrato-0001-03,CDB
0002,contrato-0002-01,LCI
0002,contrato-0002-02,SEGURO
0002,contrato-0002-03,CONSORCIO
```

O nome `id_conta` deve existir nos dois arquivos. O gerador usa esse campo como chave para encontrar os contratos da conta selecionada:

```text
identificadores.csv -- id_conta --> contratos.csv
```

Os identificadores devem ser lidos como strings para preservar zeros à esquerda. O campo `cnpj` de nove caracteres alfanuméricos é sintético e não representa um CNPJ fiscal válido.

### Geração de transações

O `DataCreator` realiza as seguintes etapas:

1. Lê os identificadores do `identificadores.csv`.
2. Lê os contratos do `contratos.csv` e cria uma estrutura indexada por `id_conta`.
3. Seleciona uma conta e busca os contratos associados ao `id_conta` dela.
4. Gera os registros transacionais.
5. Retorna os registros para o `LambdaHandler`.

O contrato de dados do desafio define `id_conta` e `cod_agencia` como strings. Também descreve os campos transacionais como identificador da transação, contrato, tipo de lançamento, valor, datas, classificação COSIF e indicador de estorno. <sup class="citation">2</sup>

### Execução da Lambda

#### Configuração

Configure as seguintes variáveis de ambiente:

- `BUCKET_DESTINO`: bucket S3 de destino.
- `PREFIXO_DESTINO`: prefixo em que os Parquet serão gravados.

A role de execução da Lambda precisa de `s3:PutObject` no prefixo de saída. Como o CSV está no pacote implantado, não é necessário `s3:GetObject` para lê-lo.

Se o arquivo não tiver um ponto de entrada de nível de módulo, inclua no `handler.py`:

```python
def lambda_handler(event, context):
    """Ponto de entrada da função AWS Lambda."""
    return LambdaHandler().executar(event or {})
```

Configure o campo **Manipulador** da Lambda como:

```text
handler.lambda_handler
```

#### Evento de teste

```json
{
  "quantidade": 1000,
  "data_particao": "2025-02-10T14:30:00Z"
}
```

`quantidade` é o número de transações a gerar. A quantidade de contas disponíveis é determinada pelas linhas do CSV.

### Saída no S3

Os registros são gravados em formato Parquet com compressão Zstandard, em um caminho particionado por ano, mês, dia e hora UTC:

```text
<prefixo>/AAAA/MM/DD/HH/part-<uuid>.parquet
```

## Bronze

## Silver

## Gold