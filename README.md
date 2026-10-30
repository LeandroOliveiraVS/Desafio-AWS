# Projeto Desafio AWS- Engenharia de dados

## Visão geral
Este projeto está sendo desenvolvido como solução para um desafio de engenharia de dados.

### Contexto do problema

A área financeira do Itaú Unibanco necessita calcular diariamente o saldo consolidado de conta corrente por contrato para toda a sua base
de clientes. Este processo é crítico para a contabilidade regulatória e para a conciliação de balanço.

Para atender a essa necessidade, o projeto implementa um pipeline de dados na AWS em camadas: uma etapa de geração de transações fictícias,
que simula a origem dos dados, seguida das camadas Bronze (dados brutos), Silver (dados validados e padronizados) e Gold (visões de negócio).
O saldo diário consolidado é entregue pela business view `saldo_conta_por_contrato` da camada Gold.

## Arquitetura
![Architecture](docs/architecture.png)

## Estrutura
```
.
├── generate_layer/                 # 1. Geração de dados fictícios (Lambda)
│   ├── app/
│   │   ├── src/data_generator/
│   │   │   ├── contas.csv
│   │   │   ├── contratos.csv
│   │   │   ├── data_faker.py
│   │   │   └── handler.py
│   │   ├── tests/
│   │   │   ├── test_faker.py
│   │   │   └── test_handler.py
│   │   ├── lambda_function.py
│   │   └── requirements.txt
│   └── infra/
│       └── scripts/build_layer.sh
├── sor_layer/                      # 2. Bronze (Glue)
│   ├── app/
│   │   ├── src/
│   │   │   ├── raw_processor_job.py
│   │   │   ├── raw_transformacoes.py
│   │   │   └── raw_processor.py   # versão anterior, em arquivo único
│   │   └── tests/test_raw_transformacoes.py
│   └── infra/
├── sot_layer/                      # 3. Silver (Glue)
│   ├── app/
│   │   ├── src/
│   │   │   ├── sot_job.py
│   │   │   └── sot_transform.py
│   │   └── tests/test_sot_transform.py
│   └── infra/
├── spec_layer/                     # 4. Gold (Glue)
│   ├── app/
│   │   ├── src/
│   │   │   ├── business_views/
│   │   │   │   └── saldo_conta_por_contrato.py
│   │   │   ├── spec_job.py
│   │   │   └── spec_transform.py
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── test_saldo_conta_por_contrato.py
│   │       └── test_spec_transform.py
│   └── infra/
├── infra/                          # Recursos compartilhados: bucket do data lake, Step Functions e gatilho por eventos (SQS)
├── docs/
├── requirements.txt
├── .gitignore
├── .env
└── README.md
```

Cada pasta `infra/` é um projeto Terraform independente (`terraform init`/`apply` dentro dela).

## 1.Geração de dados fictícios
A Lambda funciona como etapa de simulação da origem dos dados:

- `DataCreator` lê os identificadores das contas e associa contratos fictícios.
- `LambdaHandler` gera os registros, cria um arquivo Parquet usando Polars e grava o resultado no S3.
- Os identificadores da conta: `id_conta`, `cod_agencia` e `cnpj` são lidos do CSV `contas.csv` e armazenados como strings para preservar zeros à esquerda.
- Os identificadores dos contratos: `id_contrato` e `tipo_contrato` são lidos do CSV `contratos.csv` utilizando o `id_conta`.
- Os demais dados da transação, valores e datas, são gerados para fins de teste.

#### `contas.csv`

Contém os identificadores das contas:

```csv
id_conta,cod_agencia,cnpj
2960,3719,09LY7FEP8ZZ7M
0003,6157,0L8KQFJRQH9QW
```

#### `contratos.csv`

Contém os contratos associados a cada conta:

```csv
id_contrato,tipo_contrato,id_conta
87f5fd2e-069d-4931-9af4-09c4a529fe06,SEGURO,2960
1ca63482-772c-4fcf-a4f1-132386c7d5d7,CC,0003
```

O nome `id_conta` deve existir nos dois arquivos. O gerador usa esse campo como chave para encontrar os contratos da conta selecionada:

```text
contas.csv -- id_conta --> contratos.csv
```

Os identificadores devem ser lidos como strings para preservar zeros à esquerda. O campo `cnpj` de treze caracteres alfanuméricos é sintético e não representa um CNPJ fiscal válido.

### Geração de transações

O `DataCreator` realiza as seguintes etapas:

1. Lê os identificadores do `contas.csv`.
2. Lê os contratos do `contratos.csv` e cria uma estrutura indexada por `id_conta`.
3. Seleciona uma conta e busca os contratos associados ao `id_conta` dela.
4. Gera os registros transacionais.
5. Retorna os registros para o `LambdaHandler`.

Todos os registros de uma execução recebem o mesmo `id_lote`, o que permite identificar e reprocessar cada lote gerado.

#### Tipos e valores dos lançamentos

O `tipo_lancamento` é `CREDITO` (entrada de dinheiro) ou `DEBITO` (saída). Para cada lançamento é sorteado um `tipo_produto` do respectivo
tipo, e o `valor_lancamento` é sorteado dentro da faixa do produto (atributo `_PERFIL_LANCAMENTO` do `DataCreator`):

| Lançamento | Produto | Peso no lançamento | Faixa de valor |
|---|---|---|---|
| `CREDITO` (40%) | `PIX_RECEBIDO` | 55% | 10,00 a 3.000,00 |
| | `TED_RECEBIDA` | 15% | 100,00 a 8.000,00 |
| | `DEPOSITO` | 15% | 50,00 a 2.000,00 |
| | `SALARIO` | 10% | 1.500,00 a 8.000,00 |
| | `RESGATE_INVESTIMENTO` | 5% | 100,00 a 5.000,00 |
| `DEBITO` (60%) | `PIX_ENVIADO` | 40% | 10,00 a 3.000,00 |
| | `COMPRA_DEBITO` | 28% | 5,00 a 800,00 |
| | `PAGAMENTO_BOLETO` | 23% | 50,00 a 5.000,00 |
| | `SAQUE` | 9% | 20,00 a 1.500,00 |

Os pesos e as faixas foram calibrados para que as entradas e as saídas se equilibrem: em média um lançamento soma cerca de +60, e os saldos
ficam distribuídos em torno de zero, com leve viés positivo. O valor é sempre positivo, com duas casas decimais; o sinal (entrada ou saída)
é aplicado na Silver, na coluna `valor_assinado`. O `flag_estorno` é verdadeiro em cerca de 5% dos registros.

#### Erros propositais

Para exercitar as regras de qualidade da Silver, o gerador pode criar erros de propósito. Com `taxa_erros` maior que zero, cada registro tem essa
chance de ser gerado com erro, sendo metade das vezes:

- **chave nula**: `id_transacao`, `id_conta` ou `id_contrato` é gravado como nulo;
- **duplicata**: o registro é substituído por uma cópia de um registro anterior do mesmo lote (mesmo `id_transacao`).

A quantidade total de registros não muda, e a contagem dos erros injetados é registrada no log e devolvida na resposta da Lambda (`erros_injetados`).

O contrato de dados do desafio define `id_conta` e `cod_agencia` como strings. Também descreve os campos transacionais como identificador da transação, contrato, tipo de lançamento, valor, datas, classificação COSIF e indicador de estorno.

### Execução da Lambda

#### Configuração

A Lambda é criada pelo Terraform (veja "Infraestrutura"), que já define as variáveis de ambiente:

- `BUCKET_DESTINO`: bucket S3 de destino.
- `PREFIXO_DESTINO`: prefixo em que os Parquet serão gravados.

A role de execução da Lambda precisa de `s3:PutObject` no prefixo de saída. Como o CSV está no pacote implantado, não é necessário `s3:GetObject` para lê-lo.

O ponto de entrada é a função `lambda_handler` do `generate_layer/app/lambda_function.py`, configurada no campo **Manipulador** como:

```text
generate_layer.app.lambda_function.lambda_handler
```

#### Evento de teste

```json
{
  "quantidade": 1000,
  "data_particao": "2025-02-10T14:30:00Z",
  "taxa_erros": 0.02
}
```

- `quantidade`: número de transações a gerar (padrão 1000). A quantidade de contas disponíveis é determinada pelas linhas do CSV.
- `data_particao`: data e hora da partição; sem ela, é usada a data e hora UTC da execução.
- `taxa_erros`: fração (0 a 1) dos registros gerados com erro proposital (padrão 0).

### Infraestrutura (Terraform)

A infraestrutura da camada fica em `generate_layer/infra/` e cria:

- O bucket de destino (`desafio-aws-contratos`) já existe e é apenas referenciado, não é criado pelo Terraform.
- Lambda Layer com `polars` e `Faker` (`generate_layer/app/requirements.txt`). O zip passa de 50 MB e por isso é publicado no prefixo `artefatos/` do bucket de destino.
- Lambda `data-generator` (Python 3.12) com o código e os CSVs de contas/contratos, gravando em `contratos/`.
- Agendamento no EventBridge Scheduler de segunda a sexta às 6h, 14h e 20h (`America/Sao_Paulo`), gerando `quantidade_registros` transações com `taxa_erros` (padrão 0,02) de erros propositais.
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

### Histórico dos dados

Os arquivos de `contratos/` gerados antes da versão atual do gerador (com os tipos `TARIFA`, `IOF` e `JUROS` e sem a coluna `tipo_produto`)
foram convertidos para o formato atual em 27/10/2026 e reprocessados pela pipeline:

- `tipo_lancamento`: `TARIFA` e `IOF` viraram `DEBITO`; `JUROS` virou `CREDITO` nos contratos `POUP`, `CDB` e `LCI` (rendimento) e `DEBITO`
  nos demais, preservando o sinal que cada lançamento tinha.
- `tipo_produto`: sorteado entre os produtos do lançamento cuja faixa contém o valor (ou a faixa mais próxima), com os pesos do gerador.
- Os demais campos, inclusive os valores, não foram alterados. Por isso, o histórico mantém a distribuição de valores do gerador antigo,
  com mais saídas que entradas, e os saldos desse período são majoritariamente negativos.

Os arquivos originais, antes da conversão, estão em `s3://desafio-aws-contratos/contratos_legado/pre_tipo_produto/`, com os mesmos caminhos.

## 2.Bronze (sor)
A camada Bronze é executada no `AWS Glue` que extrai os dados fictícios gerados na etapa anterior de bucket no `S3` e salva os dados no formato `Iceberg`
no prefixo `bronze/` do bucket do data lake (`desafio-aws-datalake`) e no catalógo do glue, no database `bronze`. A execução é orquestrada pelo `AWS Step Functions`.

A Bronze carrega os dados **da forma que são**: não seleciona colunas, não converte tipos e não descarta registros. Colunas novas, colunas extras
e registros com chaves nulas ou duplicados chegam à Bronze como vieram da origem; a validação e a padronização ficam a cargo da Silver.

Os dados são gravados em Iceberg V3 e em uma versão alternativa com o sufixo `_alt` (Iceberg V2), criada devido à incompatibilidade do Iceberg V3
com o Athena. As tabelas `bronze.transacoes` e `bronze.transacoes_alt` são particionadas por `dt_processamento`; se a tabela já existir, apenas as
partições presentes nos dados são substituídas.

### Evolução de schema

Os arquivos de origem podem ter schemas diferentes ao longo do tempo (por exemplo, a coluna `tipo_produto` existe apenas nos arquivos gerados após
a sua criação). Para que nenhuma coluna seja perdida:

- **Leitura**: os Parquet são lidos com `mergeSchema`, que junta as colunas de todos os arquivos; as colunas ausentes em um arquivo ficam nulas
  nos registros dele. Sem essa opção, o Spark usaria o schema de um único arquivo e poderia descartar colunas sem aviso.
- **Gravação**: as tabelas aceitam evolução de schema (propriedade `write.spark.accept-any-schema` e gravação com `mergeSchema`). Uma coluna nova
  na origem é acrescentada à tabela na próxima execução, sem necessidade de recriá-la. A propriedade também é aplicada às tabelas já existentes.
- **Ordem das colunas**: antes de gravar em uma tabela existente, as colunas são reordenadas na ordem da tabela, com as colunas novas no fim
  (método `ordenar_como_tabela`). Sem isso, o Iceberg recusa a gravação quando a origem muda a posição de uma coluna ou acrescenta uma coluna no meio.

O código fica dividido em dois arquivos:

- `raw_processor_job.py`: script do job, que lê os parâmetros, lê os Parquet de origem e grava as tabelas.
- `raw_transformacoes.py`: classe `Bronze` com a leitura da origem e a gravação das tabelas, sem dependência do `awsglue`, o que permite testá-la
  localmente com PySpark e pytest.

### Parâmetros do job Glue

| Parâmetro | Exemplo | Uso |
|---|---|---|
| `--bucket_origem` | `desafio-aws-contratos` | Bucket de origem; os Parquet são lidos do prefixo `contratos/`. |
| `--bucket_bronze` | `desafio-aws-datalake` | Bucket do data lake (o warehouse das tabelas é definido no `--conf`). |
| `--extra-py-files` | `s3://<bucket-artefatos>/scripts/raw_transformacoes.py` | Disponibiliza o `raw_transformacoes.py` para o job. |
| `--datalake-formats` | `iceberg` | Habilita o formato Iceberg no job. |
| `--conf` | Configurações Spark do Iceberg | Define extensões, catálogo, warehouse (`s3://desafio-aws-datalake/bronze/`) e implementação de I/O. |

### Testes

```bash
.venv/bin/python -m pytest sor_layer/app/tests
```

## 3.Silver (sot)
A camada Silver é executada no `AWS Glue` e lê a tabela Iceberg `bronze.transacoes` pelo catálogo do Glue. Como a Bronze guarda os dados da forma que
chegam, a Silver é a primeira camada com colunas e tipos definidos: ela aplica o schema, as regras de qualidade, padroniza e enriquece os dados, e
grava o resultado no formato `Iceberg` no prefixo `silver/` do bucket do data lake e no catálogo do glue, no database `silver`.

Assim como na Bronze, são gravadas duas tabelas particionadas por `dt_processamento`: `silver.transacoes` (Iceberg V3) e `silver.transacoes_alt` (Iceberg V2),
esta última para leitura pelo Athena. Se a tabela já existir, apenas as partições presentes nos dados são substituídas. As tabelas aceitam evolução de
schema: colunas novas são acrescentadas na próxima execução, sem necessidade de recriá-las, e as colunas são gravadas na ordem da tabela
existente, como na Bronze.

O código fica dividido em dois arquivos:

- `sot_job.py`: script do job, que lê os parâmetros, chama as regras e grava as tabelas.
- `sot_transform.py`: classe `SotTransform` com as regras, sem dependência do `awsglue`, o que permite testá-las localmente com PySpark e pytest.

### Schema

Antes das regras de qualidade, a Silver seleciona da Bronze as colunas abaixo, nesta ordem, convertidas para os tipos esperados
(atributo `SCHEMA_SILVER`). Colunas da Bronze fora desta lista não passam para a Silver; se faltar alguma coluna, o job falha com uma mensagem
indicando as colunas ausentes.

| Coluna | Tipo |
|---|---|
| `id_transacao`, `id_contrato`, `id_conta`, `cnpj`, `cod_agencia` | `string` |
| `tipo_contrato`, `tipo_lancamento`, `tipo_produto` | `string` |
| `valor_lancamento` | `decimal(18,2)` |
| `dt_lancamento` | `timestamp` |
| `dt_processamento` | `date` |
| `cod_cosif`, `id_lote` | `string` |
| `flag_estorno` | `boolean` |

Se um arquivo de origem não tiver alguma coluna (por exemplo, `tipo_produto`), ela chega nula da Bronze.

### Regras de qualidade

As regras são aplicadas antes das transformações, nesta ordem:

1. **Chaves obrigatórias**: registros com `id_transacao`, `id_conta`, `id_contrato` ou `dt_processamento` nulos (ou texto vazio) são separados, com o motivo
   da rejeição (ex.: `chave nula: id_conta, id_contrato`).
2. **Tipo de lançamento**: registros com `tipo_lancamento` diferente de `CREDITO` e `DEBITO` são separados (ex.: `tipo_lancamento inválido: JUROS`).
   Os tipos antigos `TARIFA`, `IOF` e `JUROS` já foram convertidos na origem (veja "Histórico dos dados"); a regra protege contra novos casos.
3. **Duplicatas**: é mantido um registro por `id_transacao`, o de `dt_processamento` mais recente (desempate por `dt_lancamento` e `id_lote`); os demais são separados.

Os registros separados são gravados na tabela `silver.transacoes_rejeitadas` (Iceberg V2), com a coluna `motivo_rejeicao` e as colunas de auditoria
`dt_load_sot` e `id_execucao`, que permitem saber em qual execução cada registro foi rejeitado.

### Data Quality (AWS Glue Data Quality)

Depois das regras de qualidade e das transformações, os dados que serão gravados na Silver são avaliados pelo **AWS Glue Data Quality**, com o
ruleset em DQDL gerado por `SotTransform.regras_data_quality()`:

| Regra | DQDL |
|---|---|
| `id_transacao` deve ser único globalmente | `IsUnique "id_transacao"` |
| `valor_lancamento > 0` (estornos usam `flag_estorno = true`) | `ColumnValues "valor_lancamento" > 0` |
| `dt_lancamento <= dt_processamento` | `CustomSql` que conta lançamentos com data (UTC) posterior a `dt_processamento`; um lançamento no próprio dia do processamento é válido. |
| Completude: campos NOT NULL sem nulos | `IsComplete` em cada coluna do schema da Silver (`COLUNAS_NOT_NULL`) |
| Completude: campos NOT NULL sem valores vazios | `CustomSql` que conta textos vazios ou só com espaços |

Como a Silver relê toda a Bronze a cada execução, a unicidade de `id_transacao` vale para toda a base, não só para o lote do dia.

O Data Quality **só monitora**: o resultado é publicado no console do Glue Data Quality e como métricas no CloudWatch (namespace `Glue Data Quality`),
no contexto de avaliação `silver_transacoes`, e as regras com falha aparecem no log do job com o prefixo `[DATA QUALITY]`. Uma regra com falha, ou um
erro na própria avaliação, não impede a gravação da Silver; a separação de registros inválidos continua sendo feita pelas regras de qualidade acima.

A role do job tem permissão `glue:PublishDataQuality` para publicar os resultados. As consultas das regras `CustomSql` são testadas localmente com
PySpark, executadas sobre uma tabela `primary`, como no Glue Data Quality.

### Transformações

| Coluna | Regra |
|---|---|
| `tipo_contrato`, `tipo_lancamento`, `tipo_produto`, `cod_cosif` | Padronizados com `trim` e letras maiúsculas. |
| `categoria_produto` | `CC` e `POUP` → `CONTA`; `CDB` e `LCI` → `INVESTIMENTO`; `SEGURO` e `CONSORCIO` mantêm o nome. Contrato não mapeado fica nulo. |
| `ano_mes` | Mês do lançamento no horário de Brasília (`America/Sao_Paulo`), no formato `AAAA-MM`. |
| `dias_ate_processamento` | Dias entre a data do lançamento e `dt_processamento` (ambos em UTC). |
| `valor_assinado` | `valor_lancamento` com sinal: positivo para entrada de dinheiro na conta do cliente e negativo para saída (regra abaixo). |
| `dt_load_sot` | Data e hora (UTC) da carga Silver; o mesmo valor para todas as linhas e tabelas de uma execução. |
| `id_execucao` | `JOB_RUN_ID` da execução do Glue que gravou a linha. |

O sinal de `valor_assinado` segue a natureza do lançamento (atributo `NATUREZA_LANCAMENTO`):

- `CREDITO` é positivo e `DEBITO` é negativo.
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

## 4.Gold (spec)
A camada Gold é executada no `AWS Glue` e gera as **business views**: tabelas prontas para consumo, calculadas a partir das tabelas da Silver.
O resultado é gravado no formato `Iceberg` no prefixo `gold/` do bucket do data lake e no catálogo do glue, no database `gold`.

Cada business view gera duas tabelas com o nome da view: `gold.<view>` (Iceberg V3) e `gold.<view>_alt` (Iceberg V2), esta última para
leitura pelo Athena. As tabelas aceitam evolução de schema: uma coluna nova na view é acrescentada às tabelas na próxima execução, sem
necessidade de recriá-las, e as colunas são gravadas na ordem da tabela existente, como na Bronze.

### Estrutura das business views

Um único job Glue atende todas as views. A view a executar é informada em cada execução pelo parâmetro `--business_view`:

- `spec_transform.py`: classe abstrata `SpecTransform`, base de todas as views. Fornece a leitura pelo catálogo, a criação do database e a
  gravação das tabelas, e define o método abstrato `create_business_view(df)`, que cada view implementa com a sua regra de negócio.
- `business_views/`: um arquivo por business view, com uma única classe que herda `SpecTransform`.
- `spec_job.py`: script do job, que carrega a view pelo nome, lê a tabela de origem, chama `create_business_view` e grava as tabelas.

O nome do arquivo (sem `.py`) é o valor de `--business_view` e também o nome da tabela Gold; por isso deve ser um nome válido de módulo Python,
em letras minúsculas (ex.: `saldo_conta_por_contrato`). O nome da classe é livre.

```python
# business_views/minha_view.py
from spec_transform import SpecTransform


class MinhaView(SpecTransform):
    COLUNAS_PARTICAO = ("dt_processamento",)  # opcional; () grava sem partição

    def create_business_view(self, df):
        ...
```

Para publicar uma nova view, basta criar o arquivo e rodar `terraform apply` em `spec_layer/infra`: o `spec_transform.py` e o pacote
`business_views/` são empacotados em um zip enviado ao job pelo `--extra-py-files`, sem outras mudanças na infraestrutura. Para que a view
rode na orquestração, acrescente o nome dela à variável `business_views` em `infra/variables.tf`.

### Business view: `saldo_conta_por_contrato`

Saldo diário consolidado da conta corrente (`tipo_contrato = CC`) por contrato, para toda a base de clientes.

| Coluna | Descrição |
|---|---|
| `data_saldo` | Dia do saldo, pela data do lançamento no horário de Brasília. Coluna de partição. |
| `id_contrato`, `id_conta`, `cod_agencia`, `cnpj` | Identificação do contrato e da conta. |
| `movimento_dia` | Soma do `valor_assinado` dos lançamentos do dia (0 nos dias sem movimento). |
| `qtd_lancamentos` | Quantidade de lançamentos do dia. |
| `saldo` | Saldo acumulado do contrato até o dia. |
| `saldo_mes` | Saldo do mês: soma do `movimento_dia` desde o primeiro dia do mês até o dia; reinicia a cada mês. |

- Cada contrato tem uma linha por dia, do primeiro lançamento até a data mais recente da base, inclusive nos dias sem movimento,
  em que o saldo do dia anterior se mantém.
- A origem não informa saldo inicial: todo contrato começa com saldo zero.
- A view é recalculada por completo a cada execução, porque a Silver recebe lançamentos com até 30 dias de atraso, que alteram saldos de dias anteriores.

```sql
-- Saldo de cada contrato na data mais recente
SELECT id_contrato, saldo
FROM gold.saldo_conta_por_contrato_alt
WHERE data_saldo = (SELECT max(data_saldo) FROM gold.saldo_conta_por_contrato_alt)
ORDER BY saldo DESC;
```

### Parâmetros do job Glue

| Parâmetro | Exemplo | Uso |
|---|---|---|
| `--business_view` | `saldo_conta_por_contrato` | View a executar; obrigatório e informado em cada execução. |
| `--tabela_origem` | `glue_catalog.silver.transacoes` | Tabela da Silver lida pelo catálogo e entregue a `create_business_view`. |
| `--database_destino` | `gold` | Database das tabelas da Gold, criado se não existir. |
| `--extra-py-files` | `s3://<bucket-artefatos>/scripts/spec_libs.zip` | Zip com o `spec_transform.py` e o pacote `business_views`. |
| `--datalake-formats` | `iceberg` | Habilita o formato Iceberg no job. |
| `--conf` | Configurações Spark do Iceberg | Define extensões, catálogo, warehouse (`s3://desafio-aws-datalake/gold/`) e implementação de I/O. |

O job aceita até 3 execuções simultâneas (variável `max_execucoes_simultaneas`), uma por view. Para executar uma view manualmente:

```bash
aws glue start-job-run --job-name aws-desafio-spec-etl-job \
  --arguments '{"--business_view":"saldo_conta_por_contrato"}'
```

### Testes

```bash
.venv/bin/python -m pytest spec_layer/app/tests
```

## Orquestração (Step Functions)

A state machine `aws-desafio-state-machine` (`infra/sfn.tf`) executa as camadas em sequência, usando a integração síncrona do Glue (`startJobRun.sync`):
cada etapa aguarda a conclusão do job antes de seguir.

```text
Bronze (aws-desafio-sor-etl-job) -> Silver (aws-desafio-sot-etl-job) -> Gold (aws-desafio-spec-etl-job, uma execução por business view)
```

Na etapa Gold, cada business view listada na variável `business_views` (`infra/variables.tf`) roda em paralelo, como uma execução do job Gold
com o parâmetro `--business_view`. Para incluir uma nova view na orquestração, basta acrescentar o nome do arquivo à lista.

- Se um job falhar, a etapa faz até duas tentativas adicionais, com intervalo de duas horas entre as tentativas.
- Se todas as tentativas falharem, a execução do workflow termina com falha e as etapas seguintes não são executadas.
- A saída de cada etapa guarda o nome do job, o `JobRunId` e o estado final da execução.
- O primeiro estado (`Inicio`) guarda a entrada da execução no campo `gatilho`. Assim a state machine aceita tanto o lote de mensagens
  enviado pelo gatilho por eventos quanto uma execução manual com `{}`, e o histórico registra quais arquivos dispararam cada execução.

### Gatilho por eventos (S3 → SQS → Step Functions)

A state machine é iniciada automaticamente quando a Lambda grava um novo arquivo de contratos (`infra/events.tf`):

```text
Lambda grava .parquet -> S3 (desafio-aws-contratos/contratos/) -> SQS -> EventBridge Pipe -> Step Functions
                                                                  └-> DLQ (mensagens com falha)
```

- **Notificação do bucket**: eventos `s3:ObjectCreated:*` de arquivos `.parquet` no prefixo `contratos/` são enviados para a fila
  `aws-desafio-contratos`. A fila só aceita mensagens do S3 vindas do bucket de contratos da própria conta.
- **Fila e DLQ**: mensagens que falharem 3 vezes vão para a fila `aws-desafio-contratos-dlq`, onde ficam por 14 dias para investigação.
- **EventBridge Pipe** (`aws-desafio-contratos-sfn`): lê a fila e inicia a state machine. Arquivos que chegam em até 5 minutos (ou até
  10 mensagens) são agrupados em uma única execução. O pipe só repassa eventos de arquivo criado; o evento de teste que o S3 envia ao
  configurar a notificação é descartado.

Como a Bronze lê todo o prefixo `contratos/` e aceita uma execução por vez, arquivos que chegam com poucos minutos de diferença, mas em lotes
diferentes, geram uma segunda execução que aguarda a retentativa da Bronze. No uso normal (três cargas por dia, com horas de intervalo) isso não ocorre.

O recurso `aws_s3_bucket_notification` controla todas as notificações do bucket de contratos: notificações criadas fora do Terraform são removidas no próximo `apply`.

Para acompanhar as execuções e verificar mensagens com falha:

```bash
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:<conta>:stateMachine:aws-desafio-state-machine \
  --max-items 3 --query 'executions[].[name,status,startDate]'

aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name aws-desafio-contratos-dlq --query QueueUrl --output text) \
  --attribute-names ApproximateNumberOfMessages
```
