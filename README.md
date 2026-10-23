# Projeto Desafio AWS- Engenharia de dados

## Visão geral
Este projeto está sendo desenvolvido como solução para um desafio de engenharia de dados.

## Arquitetura
![Architecture](docs/architecture.png)

## Estrutura
```
.
├── generate_layer/
│   ├── app/
│   │   ├── src/
│   │   │   └── data_generator/
│   │   │       ├── data_faker.py
│   │   │       └── handler.py
│   │   ├── tests/
│   │   │   ├── test_handler.py
│   │   │   └── test_data_faker.py
│   │   └── lambda_function.py
│   └── infra/
├── sor_layer/
│   ├── app/
│   │   ├── src/
│   │   └── tests/
│   └── infra/
├── sot_layer/
│   ├── app/
│   │   ├── src/
│   │   └── tests/
│   └── infra/
├── spec_layer/
│   ├── app/
│   │   ├── src/
│   │   └── tests/
│   └── infra/
├── docs/
├── requirements.txt
├── .gitignore
├── .env
└── README.md
```

## 1.Geração de dados fictícios
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

### Infraestrutura (Terraform)

A infraestrutura da camada fica em `generate_layer/infra/` e cria:

- O bucket de destino (`desafio-aws-contratos`) já existe e é apenas referenciado, não é criado pelo Terraform.
- Lambda Layer com `polars` e `Faker` (`generate_layer/app/requirements.txt`). O zip passa de 50 MB e por isso é publicado no prefixo `artefatos/` do bucket de destino.
- Lambda `data-generator` (Python 3.12) com o código e os CSVs de contas/contratos, gravando em `contratos/`.
- Agendamento no EventBridge Scheduler de segunda a sexta às 6h, 14h e 20h (`America/Sao_Paulo`), gerando `quantidade_registros` transações.
- Roles IAM com permissão mínima (`s3:PutObject` no prefixo de saída e `lambda:InvokeFunction` para o agendamento) e log group no CloudWatch.

```bash
./generate_layer/infra/scripts/build_layer.sh   # gera infra/build/layer.zip
cd generate_layer/infra
terraform init
terraform plan
terraform apply
```

Rode o `build_layer.sh` novamente sempre que `generate_layer/app/requirements.txt` mudar. As variáveis (agendamento, quantidade, memória, etc.) estão em `variables.tf`.

### Saída no S3

Os registros são gravados em formato Parquet com compressão Zstandard, em um caminho particionado por ano, mês, dia e hora UTC:

```text
<prefixo>/AAAA/MM/DD/HH/part-<uuid>.parquet
```

## 2.Bronze (sor)
A camada Bronze é executada no `AWS Glue` que extrai os dados fictícios gerados na etapa anterior de bucket no `S3` e salva os dados no formato `Iceberg`
no prefixo `bronze/` do bucket do data lake (`desafio-aws-datalake`) e no catalógo do glue, no database `bronze`. A execução é orquestrada pelo `AWS Step Functions`.

A leitura dos dados é feita via DynamicFrame e passada para Dataframe e escrita em Iceberg V3 e uma versão alternativa com o sufixo `_alt` é criada
devido a incompatibilidade do Iceberg V3 com Athena.

### Parâmetros do job Glue

| Parâmetro | Exemplo | Uso |
|---|---|---|
| `--bucket_origem` | `<nome-do-bucket-origem>` | Bucket de origem dos Parquet. |
| `--bucket_bronze` | `<nome-do-bucket-bronze>` | Bucket usado como warehouse da tabela Iceberg. |
| `--datalake-formats` | `iceberg` | Habilita o formato Iceberg no job. |
| `--conf` | Configurações Spark do Iceberg | Define extensões, catálogo, warehouse e implementação de I/O. |

## 3.Silver (sot)
A camada Silver é executada no `AWS Glue` e lê a tabela Iceberg `bronze.transacoes` pelo catálogo do Glue. Ela aplica as regras de qualidade, padroniza
e enriquece os dados, e grava o resultado no formato `Iceberg` no prefixo `silver/` do bucket do data lake e no catálogo do glue, no database `silver`.

Assim como na Bronze, são gravadas duas tabelas particionadas por `dt_processamento`: `silver.transacoes` (Iceberg V3) e `silver.transacoes_alt` (Iceberg V2),
esta última para leitura pelo Athena. Se a tabela já existir, apenas as partições presentes nos dados são substituídas.

O código fica dividido em dois arquivos:

- `sot_job.py`: script do job, que lê os parâmetros, chama as regras e grava as tabelas.
- `sot_transform.py`: classe `SotTransform` com as regras, sem dependência do `awsglue`, o que permite testá-las localmente com PySpark e pytest.

### Regras de qualidade

As regras são aplicadas antes das transformações, nesta ordem:

1. **Chaves obrigatórias**: registros com `id_transacao`, `id_conta`, `id_contrato` ou `dt_processamento` nulos (ou texto vazio) são separados, com o motivo
   da rejeição (ex.: `chave nula: id_conta, id_contrato`).
2. **Duplicatas**: é mantido um registro por `id_transacao`, o de `dt_processamento` mais recente (desempate por `dt_lancamento` e `id_lote`); os demais são separados.

Os registros rejeitados ainda não são gravados em tabela: são separados e descartados.

### Transformações

| Coluna | Regra |
|---|---|
| `tipo_contrato`, `tipo_lancamento`, `cod_cosif` | Padronizados com `trim` e letras maiúsculas. |
| `categoria_produto` | `CC` e `POUP` → `CONTA`; `CDB` e `LCI` → `INVESTIMENTO`; `SEGURO` e `CONSORCIO` mantêm o nome. Contrato não mapeado fica nulo. |
| `ano_mes` | Mês do lançamento no horário de Brasília (`America/Sao_Paulo`), no formato `AAAA-MM`. |
| `dias_ate_processamento` | Dias entre a data do lançamento e `dt_processamento` (ambos em UTC). |
| `valor_assinado` | `valor_lancamento` com sinal: positivo para entrada de dinheiro na conta do cliente e negativo para saída (regra abaixo). |
| `dt_load_sot` | Data e hora (UTC) da carga Silver; o mesmo valor para todas as linhas e tabelas de uma execução. |
| `id_execucao` | `JOB_RUN_ID` da execução do Glue que gravou a linha. |

O sinal de `valor_assinado` segue a natureza do lançamento:

- `CREDITO` é positivo; `DEBITO`, `TARIFA` e `IOF` são negativos.
- `JUROS` é positivo nos contratos em que é rendimento pago ao cliente (`POUP`, `CDB`, `LCI`) e negativo nos demais (`CC`, `CONSORCIO`, `SEGURO`).
- Quando `flag_estorno` é verdadeiro, o sinal é invertido (ex.: um débito estornado devolve o dinheiro ao cliente).

### Parâmetros do job Glue

| Parâmetro | Exemplo | Uso |
|---|---|---|
| `--tabela_origem` | `glue_catalog.bronze.transacoes` | Tabela da Bronze lida pelo catálogo. |
| `--database_destino` | `silver` | Database das tabelas da Silver, criado se não existir. |
| `--extra-py-files` | `s3://<bucket-artefatos>/scripts/sot_transform.py` | Disponibiliza o `sot_transform.py` para o job. |
| `--datalake-formats` | `iceberg` | Habilita o formato Iceberg no job. |
| `--conf` | Configurações Spark do Iceberg | Define extensões, catálogo, warehouse (`s3://desafio-aws-datalake/silver/`) e implementação de I/O. |

### Testes

```bash
.venv/bin/python -m pytest sot_layer/app/tests
```

## Orquestração (Step Functions)

A state machine `aws-desafio-state-machine` (`infra/sfn.tf`) executa as camadas em sequência, usando a integração síncrona do Glue (`startJobRun.sync`):
cada etapa aguarda a conclusão do job antes de seguir.

```text
Bronze (aws-desafio-sor-etl-job) -> Silver (aws-desafio-sot-etl-job)
```

- Se um job falhar, a etapa faz até duas tentativas adicionais, com intervalo de duas horas entre as tentativas.
- Se todas as tentativas falharem, a execução do workflow termina com falha e as etapas seguintes não são executadas.
- A saída de cada etapa guarda o nome do job, o `JobRunId` e o estado final da execução.

## 4.Gold (spec)