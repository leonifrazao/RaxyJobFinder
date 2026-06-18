from __future__ import annotations

import argparse
import sys

from job_search.container import JobSearchContainer
from job_search.service import JobSearchRequest


SPLITTED_BY_COUNTRY_BASE = "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-country"
ALL_COUNTRY_FILES = [
    "Albania", "Australia", "Bosnia_and_Herzegovina", "Brazil", "Bulgaria",
    "Canada", "Czechia", "Finland", "France", "Georgia", "Germany",
    "Hong_Kong", "Hungary", "India", "Ireland", "Israel", "Italy", "Japan",
    "Latvia", "Malaysia", "Moldova", "Netherlands", "Norway", "Philippines",
    "Poland", "Russia", "Serbia", "Singapore", "South_Africa", "South_Korea",
    "Spain", "Sweden", "Switzerland", "Taiwan", "Thailand", "Turkey",
    "United_Arab_Emirates", "United_Kingdom", "United_States", "Unknown",
]
PROXY_PROVIDERS = {
    "united-states": f"{SPLITTED_BY_COUNTRY_BASE}/United_States.txt",
    "brazil": f"{SPLITTED_BY_COUNTRY_BASE}/Brazil.txt",
    "canada": f"{SPLITTED_BY_COUNTRY_BASE}/Canada.txt",
    "germany": f"{SPLITTED_BY_COUNTRY_BASE}/Germany.txt",
    "netherlands": f"{SPLITTED_BY_COUNTRY_BASE}/Netherlands.txt",
    "all": [f"{SPLITTED_BY_COUNTRY_BASE}/{c}.txt" for c in ALL_COUNTRY_FILES],
}
DEFAULT_PROVIDER = "all"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI generica para buscar vagas em portais configuraveis.")
    parser.add_argument("--portal", choices=["linkedin", "gupy", "glassdoor"], default="linkedin", help="modulo de portal de vagas")
    parser.add_argument(
        "--provider",
        choices=sorted(PROXY_PROVIDERS),
        default=DEFAULT_PROVIDER,
        help="provider F0rc3Run/splitted-by-country para usar",
    )
    parser.add_argument("--proxy-source", action="append", help="URL ou arquivo local com proxies; sobrescreve --provider. Pode ser repetido.")
    parser.add_argument("--keywords", default="Vagas", help="palavras-chave da busca")
    parser.add_argument("--location", default="Brasil", help="texto de localizacao para buscar")
    parser.add_argument("--location-id", dest="location_id", help="id da localizacao no portal; pula typeahead quando informado")
    parser.add_argument("--geo-id", dest="location_id", help="alias LinkedIn para --location-id")
    parser.add_argument("--location-choice", type=int, help="indice 1-based da localizacao retornada pelo portal")
    parser.add_argument("--valid-count", type=int, default=25, help="quantidade de proxies/bridges funcionais para manter no pool")
    parser.add_argument("--jobs-per-proxy", type=int, default=5, help="quantidade de detalhes de vagas por proxy antes de rotacionar")
    parser.add_argument("--max-count", type=int, default=177, help="quantidade maxima de configs para carregar")
    parser.add_argument("--threads", type=int, default=8, help="workers de teste de proxy")
    parser.add_argument("--timeout", type=float, default=12.0, help="timeout em segundos para busca/typeahead/teste")
    parser.add_argument("--detail-timeout", type=float, default=5.0, help="timeout em segundos para cada detalhe de vaga")
    parser.add_argument("--output", help="arquivo para salvar a resposta bruta")
    parser.add_argument("--jobs-output", help="arquivo JSON para salvar as vagas extraidas")
    parser.add_argument("--details-output", help="arquivo JSON para salvar vagas com detalhes")
    parser.add_argument("--filters", help="arquivo JSON com filtros desacoplados para considerar vagas")
    parser.add_argument("--details-limit", type=int, default=0, help="quantidade de vagas para detalhar; 0 detalha todas")
    parser.add_argument("--show-jobs", type=int, default=10, help="quantidade de vagas para mostrar na tabela")
    parser.add_argument("--gd-cookie", dest="gd_cookie", default="", help="cookie string para autenticacao no Glassdoor")
    parser.add_argument("--start", type=int, default=0, help="offset inicial para paginacao (incremento de 60)")
    parser.add_argument("--max-jobs", type=int, default=0, help="maximo de vagas para coletar via paginacao; 0 = apenas pagina inicial")
    parser.add_argument("--detail-threads", type=int, default=5, help="threads paralelas para buscar detalhes das vagas")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    portal = args.portal
    if args.proxy_source:
        proxy_sources = args.proxy_source
    else:
        provider_val = PROXY_PROVIDERS[args.provider]
        proxy_sources = provider_val if isinstance(provider_val, list) else [provider_val]
    container = JobSearchContainer()
    container.config.portal_name.from_value(portal)
    container.config.provider_name.from_value(args.provider)
    container.config.gd_cookie.from_value(args.gd_cookie)
    service = container.job_search_service()
    view = container.view()
    request = JobSearchRequest(
        proxy_sources=proxy_sources,
        keywords=args.keywords,
        location=args.location,
        location_id=args.location_id,
        location_choice=args.location_choice,
        valid_count=args.valid_count,
        jobs_per_proxy=args.jobs_per_proxy,
        max_count=args.max_count,
        threads=args.threads,
        timeout=args.timeout,
        detail_timeout=args.detail_timeout,
        raw_output=args.output or f"output/{portal}_response.html",
        jobs_output=args.jobs_output or f"output/vagas_{portal}.json",
        details_output=args.details_output or f"output/vagas_{portal}_detalhadas.json",
        filters_path=args.filters,
        details_limit=args.details_limit,
        show_jobs=args.show_jobs,
        start=args.start,
        max_jobs=args.max_jobs,
        detail_threads=args.detail_threads,
    )
    try:
        view.info(f"[bold]Portal:[/] {portal}")
        view.info(f"[bold]Provider:[/] {args.provider}")
        for i, src in enumerate(proxy_sources, 1):
            view.info(f"[bold]Fonte {i}:[/] {src}")
        view.info(f"[bold]Keywords:[/] {args.keywords}")
        view.info(f"[bold]Localizacao inicial:[/] {args.location}")
        return service.run(request)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
