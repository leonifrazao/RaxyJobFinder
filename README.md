# RaxyJobFinder

**Buscador multicanal de vagas com rotação automática de proxies.**

Raxy consulta LinkedIn, Gupy e Glassdoor em paralelo, rotaciona proxies automaticamente via bridges Xray/V2Ray, e aplica filtros inteligentes nas vagas encontradas — tudo por linha de comando.

---

## Instalação

### pip (recomendado)

```bash
pip install botasaurus dependency-injector beautifulsoup4 requests urllib3 rich
pip install /caminho/para/proxy_framework/
pip install -e .
```

Requer **Python 3.10+** e o binário do [Xray](https://github.com/XTLS/Xray-core) (ou V2Ray) no `PATH` ou apontado por `$XRAY_PATH`.

### Docker

```bash
docker build -t raxy .
```

A imagem já empacota Python, dependências e o Xray-core. Use:

```bash
docker run --rm -it -v "$PWD/output:/app/output" raxy --keywords "Python" --portal linkedin
```

### Nix (NixOS / nix-shell)

```bash
nix-shell
python buscador_vagas/buscador.py
```

O `shell.nix` configura o ambiente Python, baixa dependências faltantes e detecta automaticamente o Xray ou V2Ray do nixpkgs.

---

## Quick Start

```bash
# Buscar vagas de Python no LinkedIn (padrão)
python buscador_vagas/buscador.py --keywords "Python" --location "São Paulo"

# Resultados salvos em:
#   output/vagas.json              — vagas básicas
#   output/vagas_detalhadas.json   — vagas com descrição completa
#   output/linkedin_response.html  — resposta bruta do portal
```

---

## SDK Python (Programático)

Além da CLI, o Raxy oferece um SDK para uso diretamente em código Python. Importe `JobFinder` e obtenha os resultados como objetos tipados.

### Instalação

```bash
pip install -e .  # ou pip install buscador_vagas/
```

### Uso básico

```python
from buscador_vagas import JobFinder

finder = JobFinder(portal="linkedin", keywords="Python", location="São Paulo")
jobs = finder.search()

for job in jobs:
    print(job.summary.title, job.summary.company)
```

### Com filtro por arquivo JSON

```python
finder = JobFinder(
    portal="linkedin",
    keywords="Python",
    filters="filters/python.json",
)
jobs = finder.search()
```

### Com filtro programático

```python
from buscador_vagas import JobFinder, JobFilterSet

filtro = JobFilterSet.from_dict({
    "all": [
        {"fields": ["title"], "contains": "Python"},
        {"fields": ["criteria.Tipo"], "in": ["Remoto", "Híbrido"]},
    ]
})

finder = JobFinder(filters=filtro)
jobs = finder.search()
```

### Filtro por chamada (sobrescreve o do construtor)

```python
finder = JobFinder()

# só nesta busca aplica o filtro
jobs = finder.search(filters=filtro)

# próxima busca volta ao comportamento padrão (sem filtro)
jobs2 = finder.search()
```

### Proxy, paginação e detalhes

```python
finder = JobFinder(
    portal="gupy",
    keywords="Data Science",
    location="Rio de Janeiro",
    proxy_provider="brazil",          # proxies brasileiros
    proxy_sources=["https://meu-proxy.txt"],  # ou lista manual
    valid_count=25,                   # pool de bridges
    jobs_per_proxy=3,                 # rotaciona a cada 3 detalhes
    max_jobs=120,                     # paginação: até 120 vagas
    detail_threads=10,                # 10 threads para detalhes
    details_limit=20,                 # detalha só as 20 primeiras
    timeout=15.0,                     # timeout do proxy
    detail_timeout=8.0,               # timeout do detalhe
    silent=True,                      # sem output no terminal
)

jobs = finder.search(
    jobs_output="resultados/vagas.json",
    details_output="resultados/detalhadas.json",
)
```

### Tipos retornados

`search()` retorna `list[JobPosting]`, onde cada `JobPosting` contém:

| Atributo | Tipo | Descrição |
|---|---|---|
| `summary` | `JobSummary` | Dados básicos da vaga (título, empresa, local, URL) |
| `details` | `JobDetails \| None` | Descrição completa, critérios, texto de candidatura |
| `detail_error` | `str` | Mensagem de erro se o detalhamento falhou |

Use `job.to_dict()` para serializar em dicionário (útil para JSON).

### Todos os parâmetros do construtor

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `portal` | `"linkedin"` | `linkedin`, `gupy` ou `glassdoor` |
| `keywords` | `"Vagas"` | Termo de busca |
| `location` | `"Brasil"` | Localização |
| `location_id` | `None` | ID da localização (pula typeahead) |
| `location_choice` | `None` | Índice 1-based no typeahead |
| `proxy_sources` | `None` | Lista de URLs/arquivos de proxy |
| `proxy_provider` | `"all"` | `brazil`, `united-states`, `canada`, etc. |
| `valid_count` | `25` | Bridges no pool |
| `jobs_per_proxy` | `5` | Vagas por proxy antes de rotacionar |
| `max_count` | `177` | Máximo de configs de proxy a carregar |
| `threads` | `8` | Workers para testar proxies |
| `timeout` | `12.0` | Timeout do proxy (segundos) |
| `detail_timeout` | `15.0` | Timeout do detalhe (segundos) |
| `filters` | `None` | `JobFilterSet`, caminho de arquivo, ou `None` |
| `filters_path` | `None` | Caminho do arquivo de filtro (alternativo) |
| `details_limit` | `0` | Máx. de vagas para detalhar (`0` = todas) |
| `start` | `0` | Offset da paginação |
| `max_jobs` | `0` | Máx. de vagas via paginação (`0` = só 1ª página) |
| `detail_threads` | `5` | Threads paralelas para detalhes |
| `gd_cookie` | `""` | Cookie do Glassdoor |
| `silent` | `True` | `False` para mostrar output no terminal |

---

## Portais Suportados

| Portal | Autenticação | Como obter |
|---|---|---|
| **LinkedIn** | Pública (sem login) | — |
| **Gupy** | Pública (REST API) | — |
| **Glassdoor** | Cookie de sessão (Opcional) | Faça login no Glassdoor pelo navegador, copie o cookie e passe com `--gd-cookie` |

```bash
# LinkedIn (padrão)
python buscador_vagas/buscador.py --keywords "Desenvolvedor"

# Gupy
python buscador_vagas/buscador.py --portal gupy --keywords "Python" --location "São Paulo"

# Glassdoor (requer cookie autenticado)
python buscador_vagas/buscador.py --portal glassdoor --gd-cookie "seu_cookie_aqui" --keywords "Python"
```

---

## Funcionalidades

### Proxy automático

Raxy descobre, testa e mantém um pool de bridges HTTP via Xray/V2Ray. Os proxies são rotacionados a cada `N` vagas detalhadas para evitar bloqueios.

```bash
# Pool de 25 bridges, troca de proxy a cada 5 detalhes
python buscador_vagas/buscador.py --valid-count 25 --jobs-per-proxy 5
```

### Cache de proxies

Os proxies testados são salvos em `proxy_cache.json` para reúso. Remova o arquivo para forçar um novo teste.

### Paginação

Colete centenas de vagas com paginação automática:

```bash
python buscador_vagas/buscador.py --keywords Desenvolvedor --max-jobs 180 --start 0
```

### Filtros inteligentes

Regras de filtragem em JSON. O motor suporta operadores lógicos (`all`, `any`, `not`) e operadores de campo (`contains`, `not_contains`, `equals`, `not_equals`, `regex`, `in`, `exists`).

```bash
python buscador_vagas/buscador.py --filters filtros/python.json
```

### Threads paralelas

```bash
python buscador_vagas/buscador.py --threads 8 --detail-threads 5
```

---

## Filtros

Os filtros são arquivos JSON que você passa com `--filters`. Eles permitem incluir ou excluir vagas com base no título, descrição, localização, critérios e outros campos.

### Estrutura básica

Cada filtro é um objeto JSON com **operadores**. O operador mais simples é o `contains`:

```json
{
  "fields": ["title", "description"],
  "contains": "python"
}
```

Isso mantém apenas vagas cujo título **ou** descrição contenham "python".

### Operadores de campo

| Operador | O que faz | Exemplo |
|---|---|---|
| `contains` | O campo contém o texto (case insensitive) | `"contains": "python"` |
| `contains` (lista) | O campo contém **qualquer** item da lista | `"contains": ["estagio", "estágio"]` |
| `not_contains` | O campo **não** contém o texto | `"not_contains": "trainee"` |
| `equals` | O campo é exatamente igual ao valor | `"equals": "Remoto"` |
| `not_equals` | O campo é diferente do valor | `"not_equals": "Presencial"` |
| `regex` | O campo casa com uma expressão regular | `"regex": "python|django|flask"` |
| `in` | O campo é igual a **um dos** valores da lista | `"in": ["São Paulo", "SP"]` |
| `exists` | O campo existe e não está vazio | `"exists": true` |

Exemplos de cada operador:

```json
{ "fields": ["title"], "not_contains": "trainee" }
{ "fields": ["company"], "equals": "Google" }
{ "fields": ["location"], "regex": "(SP|RJ)" }
{ "fields": ["criteria.Tipo"], "in": ["Remoto", "Híbrido"] }
{ "fields": ["description"], "exists": true }
```

### Operadores lógicos

Combine regras com `all`, `any` e `not`:

| Operador | Efeito |
|---|---|
| `all` | Todas as sub-regras precisam ser verdade (AND) |
| `any` | Pelo menos uma sub-regra precisa ser verdade (OR) |
| `not` | A sub-regra não pode ser verdade (NOT) |

**all** — todas as condições devem ser atendidas:

```json
{
  "all": [
    { "fields": ["title"], "contains": "senior" },
    { "fields": ["location"], "contains": "remoto" }
  ]
}
```

Só passa se o título contiver "senior" **E** a localização contiver "remoto".

**any** — qualquer condição já aprova:

```json
{
  "any": [
    { "fields": ["title", "description"], "contains": "python" },
    { "fields": ["title", "description"], "contains": ["dados", "data"] }
  ]
}
```

Passa se tiver "python" **OU** "dados"/"data".

**not** — nega a condição:

```json
{
  "not": {
    "fields": ["title", "description"],
    "contains": ["estagio", "estágio", "aprendiz"]
  }
}
```

Exclui vagas que contenham "estagio", "estágio" ou "aprendiz".

Você pode aninhar livremente:

```json
{
  "all": [
    { "fields": ["title"], "contains": "python" },
    {
      "not": {
        "fields": ["title"],
        "contains": "estágio"
      }
    },
    {
      "any": [
        { "fields": ["location"], "contains": "remoto" },
        { "fields": ["location"], "contains": "hibrido" }
      ]
    }
  ]
}
```

### Campos disponíveis para filtrar

O filtro opera sobre o dicionário completo da vaga (básico + detalhado). Os campos mais comuns:

| Campo | Origem | Conteúdo |
|---|---|---|
| `title` | básico | Título da vaga |
| `company` | básico | Nome da empresa |
| `location` | básico | Localização |
| `description` | detalhado | Descrição completa |
| `criteria` | detalhado | Objeto com critérios (ex: `{"Tipo": "Remoto", "Nível": "Sênior"}`) |
| `criteria.Tipo` | detalhado | Acesso via dot notation, ex: tipo de contratação |
| `criteria.Nível` | detalhado | Nível hierárquico (Sênior, Pleno, etc.) |
| `listed_text` | básico | Texto de quando foi publicada |

Para acessar campos aninhados, use **dot notation**: `criteria.Tipo`, `criteria.Nível`.

### Como montar seu próprio filtro

1. **Execute uma busca primeiro** para gerar `output/vagas_detalhadas.json`
2. **Veja a estrutura** dos campos no JSON gerado
3. **Crie um arquivo `.json`** com as regras desejadas
4. **Passe com `--filters`**

Exemplo passo a passo:

```bash
# 1. Busca para gerar os JSONs de saída
python buscador_vagas/buscador.py --keywords "Python" --details-limit 5

# 2. Olhe o arquivo gerado para conhecer os campos
cat output/vagas_detalhadas.json | python -m json.tool | head -80

# 3. Crie seu filtro, por exemplo meu_filtro.json:
# {
#   "all": [
#     { "fields": ["title"], "contains": "senior" },
#     { "fields": ["criteria.Tipo"], "in": ["Remoto", "Híbrido"] }
#   ]
# }

# 4. Rode com o filtro
python buscador_vagas/buscador.py --keywords "Python" --filters meu_filtro.json
```

### Filtros prontos

| Arquivo | Efeito |
|---|---|
| `buscador_vagas/filters/python.json` | Apenas vagas com "python" no título ou descrição |
| `buscador_vagas/filters/python_or_data.json` | Python OU dados/data/analytics |
| `buscador_vagas/filters/senior_remote.json` | Senior E remoto |
| `buscador_vagas/filters/not_internship.json` | Exclui estágio/aprendiz |

---

## Opções da CLI

### `--portal`

Portal de vagas a consultar. Padrão: `linkedin`.

```
--portal linkedin     LinkedIn (padrão, sem autenticação)
--portal gupy         Gupy (API pública REST)
--portal glassdoor    Glassdoor (requer --gd-cookie)
```

### `--keywords`

Termo de busca. Use aspas para múltiplas palavras.

```
--keywords "Python"
--keywords "Desenvolvedor Java Sênior"
```

### `--location` / `--location-choice` / `--location-id` / `--geo-id`

Controlam o local da busca. O Raxy consulta o typeahead do portal e mostra as opções disponíveis.

```
--location "São Paulo"                  # texto da busca
--location "São Paulo" --location-choice 1   # escolhe automaticamente o 1º resultado
--location-id 106057199                 # pula o typeahead, usa o ID direto
--geo-id 106057199                      # alias do --location-id (LinkedIn)
```

### `--provider`

Fonte de proxies do repositório `F0rc3Run/splitted-by-country`. Padrão: `united-states`.

```
--provider brazil
--provider united-states
```

### `--proxy-source`

URL ou caminho local para uma lista manual de proxies. Pode repetir a flag para múltiplas fontes.

```
--proxy-source "https://exemplo.com/proxies.txt"
--proxy-source "./meus_proxies.txt" --proxy-source "https://outra-fonte.com/proxies.txt"
```

### `--valid-count`

Número alvo de bridges HTTP a manter no pool. O Raxy testa proxies até atingir esse número. Se encontrar menos, segue com os disponíveis.

```
--valid-count 25    # padrão
--valid-count 50    # pool maior = mais resiliência
```

### `--jobs-per-proxy`

Quantos detalhes de vaga cada proxy processa antes de rotacionar para o próximo. Útil para evitar bloqueio por excesso de requisições no mesmo IP.

```
--jobs-per-proxy 5    # troca de proxy a cada 5 detalhes (padrão)
--jobs-per-proxy 1    # troca a cada vaga (máximo de discrição)
--jobs-per-proxy 20   # troca só a cada 20 detalhes
```

### `--max-count`

Número máximo de proxies a testar. Corta o teste cedo se você já tiver proxies suficientes.

```
--max-count 10    # testa no máximo 10 proxies
```

### `--max-jobs` / `--start`

Paginação. `--max-jobs` define o total de vagas a coletar; `--start` define o offset inicial. A cada página o offset incrementa em 60.

```
--max-jobs 180 --start 0     # coleta 180 vagas do início
--max-jobs 300 --start 60    # começa do offset 60, coleta até 300
```

### `--timeout` / `--detail-timeout`

Timeouts em segundos. `--timeout` para o teste inicial de conectividade do proxy; `--detail-timeout` para o request de detalhe da vaga.

```
--timeout 12        # 12s para testar cada proxy (padrão)
--detail-timeout 5  # 5s para cada detalhe de vaga (padrão)
```

### `--threads` / `--detail-threads`

Paralelismo. `--threads` para testar proxies simultaneamente; `--detail-threads` para buscar detalhes de vagas em paralelo.

```
--threads 8           # 8 workers testam proxies por vez (padrão)
--detail-threads 5    # 5 threads buscam detalhes em paralelo (padrão)
```

### `--details-limit`

Limita quantas vagas serão detalhadas. Use `0` para detalhar todas.

```
--details-limit 10    # detalha só as 10 primeiras vagas
--details-limit 0     # detalha todas as vagas encontradas
```

### `--output` / `--jobs-output` / `--details-output`

Caminhos dos arquivos de saída.

```
--output output/linkedin_response.html         # HTML bruto da resposta
--jobs-output output/vagas.json                # vagas básicas
--details-output output/vagas_detalhadas.json  # vagas com descrição
```

### `--show-jobs`

Quantas vagas exibir na tabela do terminal ao final.

```
--show-jobs 20    # mostra 20 vagas na tabela
--show-jobs 50    # mostra 50 vagas na tabela
```

### `--filters`

Arquivo JSON com regras de filtragem. O motor suporta operadores `all`, `any`, `not`, `contains`, `not_contains`, `equals`, `not_equals`, `regex`, `in`, `exists` e dot notation para campos aninhados.

```
--filters filters/python.json
--filters filters/senior_remote.json
```

### `--gd-cookie`

Cookie de sessão do Glassdoor (obrigatório para o portal Glassdoor). Faça login no Glassdoor pelo navegador, abra o DevTools (F12) > Network, copie o header `Cookie` de qualquer requisição.

```
--gd-cookie "session_id=abc123; ..."
```

---

## Campos retornados

**Vagas básicas:** `provider`, `job_id`, `title`, `company`, `location`, `listed_at`, `listed_text`, `url`, `company_url`, `logo_url`, `entity_urn`, `reference_id`, `tracking_id`, `row`, `column`

**Vagas detalhadas (adicional):** `description`, `criteria`, `detail_title`, `detail_company`, `detail_location`, `detail_posted_text`, `detail_applicants_text`, `apply_text`, `detail_url`, `detail_logo_url`, `detail_status_code`, `detail_error`

---

## Arquitetura

```
buscador.py              → entrypoint
job_search/cli.py        → parser de argumentos
job_search/container.py  → injeção de dependências
job_search/domain/       → DTOs, entidades, ports, filtros
job_search/service/      → orquestração
job_search/modules/      → adaptadores dos portais (linkedin, gupy, glassdoor)
job_search/infrastructure/ → HTTP, proxy pool, repositório JSON
job_search/view/         → interface Rich (tabela, seleção interativa)
```
