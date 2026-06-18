# Buscador de Vagas

CLI generica para buscar vagas usando portais modulares. Portais implementados: **LinkedIn**, **Gupy** e **Glassdoor**.

O projeto usa `proxy_framework` para abrir bridges HTTP locais e `botasaurus.request` para os requests finais.
As dependencias da aplicacao sao resolvidas via `dependency_injector` para manter baixo acoplamento e facilitar troca de modulo/infra.

## Arquitetura

- `buscador.py`: entrypoint fino para manter o comando atual.
- `job_search/cli.py`: parse de argumentos da CLI generica.
- `job_search/container.py`: composition root com `dependency_injector`, monta providers para HTTP, repository, proxy pool, view, adapter do portal e service.
- `job_search/domain/dtos.py`: DTOs/value objects de integridade (`SearchQuery`, `LocationOption`, `JobSummary`, `JobDetails`, `JobPosting`).
- `job_search/domain/entities.py`: dominio real com regras de negocio, incluindo `JobDetailingSession` para limite de detalhamento, rotacao 1 proxy/N vagas, bloqueio de bridge ruim e fallback circular.
- `job_search/domain/ports.py`: interfaces/ports (`JobBoardAdapter`, `HttpClient`, `ProxyPool`, `JobRepository`, `JobFilterRepository`, `JobSearchView`).
- `job_search/domain/filters.py`: `JobFilterSet` — motor de regras de filtragem com operadores `all`/`any`/`not`, `contains`/`regex`/`equals`/`in`/`exists`.
- `job_search/service/job_search_service.py`: orquestracao da aplicacao independente do LinkedIn.
- `job_search/modules/linkedin/adapter.py`: modulo LinkedIn (HTML scraping + API `seeMoreJobPostings`).
- `job_search/modules/gupy/adapter.py`: modulo Gupy (API REST `employability-portal.gupy.io`).
- `job_search/modules/glassdoor/adapter.py`: modulo Glassdoor (API GraphQL/BFF, requer `--gd-cookie`).
- `job_search/infrastructure/*`: adapters de Botasaurus, proxy_framework, JSON e JSON de filtros.
- `job_search/view/rich_view.py`: view completa baseada em Rich para saida, tabelas e selecao interativa.

## Rodar

```bash
nix-shell --run 'python buscador.py'
```

Por padrao ele:

- usa `--portal linkedin`;
- usa o provider `united-states` do `F0rc3Run/splitted-by-country`;
- procura ate 25 proxies que conseguem acessar o portal;
- inicia ate 25 bridges HTTP locais;
- consulta as opcoes de localizacao do modulo do portal;
- salva a resposta bruta em `output/linkedin_response.html`;
- salva vagas basicas em `output/vagas.json`;
- salva vagas detalhadas em `output/vagas_detalhadas.json`;
- rotaciona detalhes com 1 proxy a cada 5 vagas e troca imediatamente se uma bridge falhar.

## Opcoes

```bash
nix-shell --run 'python buscador.py --portal linkedin --valid-count 25 --jobs-per-proxy 5 --max-count 177 --timeout 12 --detail-timeout 5'
```

`--valid-count` define o tamanho alvo do pool de bridges. Se menos proxies funcionarem, o script segue com as disponiveis.
`--jobs-per-proxy` define quantos detalhes de vagas cada proxy processa antes de rotacionar.
`--detail-timeout` controla o timeout papum de cada request de detalhe; o padrao e 5 segundos.
`--threads` (padrao 8) define quantos workers em paralelo testam proxies.
`--detail-threads` (padrao 5) define quantas threads paralelas buscam detalhes das vagas.

Controlar arquivos de saida e quantidade exibida na tabela:

```bash
nix-shell --run 'python buscador.py --output output/linkedin_response.html --jobs-output output/vagas.json --show-jobs 20'
```

Limitar quantas vagas serao detalhadas:

```bash
nix-shell --run 'python buscador.py --details-limit 10 --details-output output/vagas_detalhadas.json'
```

Use `--details-limit 0` para detalhar todas as vagas encontradas.

Buscar por outra palavra-chave e localizacao:

```bash
nix-shell --run 'python buscador.py --keywords "Python" --location "São Paulo"'
```

Escolher automaticamente a primeira localizacao retornada pelo portal:

```bash
nix-shell --run 'python buscador.py --keywords "Python" --location "Brasil" --location-choice 1'
```

Pular o typeahead informando o id diretamente:

```bash
nix-shell --run 'python buscador.py --keywords "Python" --location "Brasil" --location-id 106057199'
```

O alias LinkedIn `--geo-id` continua funcionando:

```bash
nix-shell --run 'python buscador.py --keywords "Python" --location "Brasil" --geo-id 106057199'
```

Filtrar vagas com regras desacopladas (arquivo JSON):

```bash
nix-shell --run 'python buscador.py --filters filters/python.json'
```

O motor de filtros suporta `all`, `any`, `not`, operadores `contains`, `not_contains`, `equals`, `not_equals`, `regex`, `in`, `exists` e dot notation para campos aninhados (ex: `criteria.Tipo`). Filtros prontos em `filters/`:

| Arquivo | Efeito |
|---|---|
| `python.json` | So vagas com "python" no titulo ou descricao |
| `python_or_data.json` | Python OU dados/data/analytics |
| `senior_remote.json` | Senior E remoto |
| `not_internship.json` | Exclui estagio/aprendiz |

Trocar provider:

```bash
nix-shell --run 'python buscador.py --provider brazil --valid-count 25'
```

Usar uma fonte manual (aceita multiplas URLs/arquivos — repita a flag):

```bash
nix-shell --run 'python buscador.py --proxy-source "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-country/United_States.txt"'
```

## Glassdoor

Requer cookie de sessao autenticado:

```bash
nix-shell --run 'python buscador.py --portal glassdoor --gd-cookie "cookie_string_aqui" --keywords "Python"'
```

Usa API GraphQL/BFF interna. Typeahead de localizacao via autocomplete proprio. Paginacao cursor-based.

## Gupy

```bash
nix-shell --run 'python buscador.py --portal gupy --keywords "Python" --location "São Paulo"'
```

Usa API REST da Gupy. Typeahead de localizacao via IBGE (estados + municipios). Paginacao via offset/limit automatica.

## Cache de proxies

O `proxy_framework` salva o resultado dos testes em `proxy_cache.json` para evitar retestar os mesmos proxies em execucoes subsequentes. Para forcar reteste, remova o arquivo de cache.

## Paginação

Para coletar mais vagas alem da página inicial, use `--max-jobs` e `--start`:

```bash
nix-shell --run 'python buscador.py --keywords Desenvolvedor --max-jobs 180 --start 0'
```

O `--start` define o offset inicial da API `seeMoreJobPostings` (padrão 0).
O `--max-jobs` define o total de vagas a coletar via paginação.
A cada página o offset incrementa 60 até atingir `--max-jobs`.

```bash
# Começa do offset 60, coleta até 300 vagas
nix-shell --run 'python buscador.py --keywords Python --max-jobs 300 --start 60'
```

## Campos

Campos basicos por vaga:

- `provider`
- `job_id`
- `title`
- `company`
- `location`
- `listed_at`
- `listed_text`
- `url`
- `company_url`
- `logo_url`
- `entity_urn`
- `reference_id`
- `tracking_id`
- `row`
- `column`

Campos adicionais no arquivo detalhado:

- `detail_title`
- `detail_company`
- `detail_company_url`
- `detail_location`
- `detail_posted_text`
- `detail_applicants_text`
- `description`
- `criteria`
- `apply_text`
- `detail_url`
- `detail_logo_url`
- `decorated_job_posting_id`
- `detail_reference_id`
- `detail_status_code`
- `detail_html_size`
- `detail_bridge_index`
- `detail_error`
