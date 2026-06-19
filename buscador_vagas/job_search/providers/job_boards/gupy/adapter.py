from __future__ import annotations

import json
from urllib.parse import urlencode

from job_search.application.dto.output.http_response import HttpResponse
from job_search.application.dto.output.search_result import SearchResult
from job_search.application.ports.http_client import HttpClient
from job_search.domain.job_details import JobDetails, extract_requisitos
from job_search.domain.job_summary import JobSummary
from job_search.domain.location_option import LocationOption
from job_search.domain.search_query import SearchQuery


GUPY_BASE_URL = "https://employability-portal.gupy.io/api/v1/jobs"
IBGE_ESTADOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
IBGE_MUNICIPIOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{}/municipios"

GUPY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://portal.gupy.io/",
    "Origin": "https://portal.gupy.io",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "DNT": "1",
    "Sec-GPC": "1",
}


class GupyJobBoardAdapter:
    name = "gupy"

    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client

    def build_search_url(self, query: SearchQuery) -> str:
        params: dict[str, str] = {}
        if query.keywords:
            params["jobName"] = query.keywords
        state, city = self._parse_location(query)
        if state:
            params["state"] = state
        if city:
            params["city"] = city
        return f"{GUPY_BASE_URL}?{urlencode(params)}"

    def get_location_options(self, bridge_url: str, location_query: str, timeout: float) -> list[LocationOption]:
        estados_resp = self.http_client.get(
            bridge_url, f"{IBGE_ESTADOS_URL}?orderBy=nome", timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        estados = json.loads(estados_resp.text)

        state_id = None
        state_name = None
        for estado in estados:
            if location_query.lower() in estado["nome"].lower() or location_query.lower() in estado["sigla"].lower():
                state_id = estado["id"]
                state_name = estado["nome"]
                break

        if not state_id:
            return [LocationOption(id="BR", name="Brasil (todas as localidades)", kind="country", provider=self.name)]

        cidades_resp = self.http_client.get(
            bridge_url, IBGE_MUNICIPIOS_URL.format(state_id) + "?orderBy=nome", timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        cidades = json.loads(cidades_resp.text)

        return [
            LocationOption(
                id=f"{state_name}|{cidade['nome']}",
                name=cidade["nome"],
                kind="city",
                provider=self.name,
                raw={"state": state_name, "city": cidade["nome"], "ibge_id": cidade.get("id")},
            )
            for cidade in cidades
            if isinstance(cidade, dict) and cidade.get("nome")
        ]

    def search_jobs(self, bridge_url: str, query: SearchQuery, timeout: float, *, max_jobs: int = 0, start: int = 0) -> SearchResult:
        search_url = self.build_search_url(query)
        all_jobs: list[JobSummary] = []
        limit = 100
        offset = start
        total = 0
        first_response = None

        while True:
            params: dict[str, str | int] = {"limit": limit, "offset": offset}
            if query.keywords:
                params["jobName"] = query.keywords
            state, city = self._parse_location(query)
            if state:
                params["state"] = state
            if city:
                params["city"] = city

            url = f"{GUPY_BASE_URL}?{urlencode(params)}"
            response = self.http_client.get(bridge_url, url, timeout, headers=GUPY_HEADERS)
            if first_response is None:
                first_response = response
            if response.status_code != 200:
                raise RuntimeError(f"status HTTP inesperado: {response.status_code}")

            data = json.loads(response.text)
            jobs = self._parse_jobs(data.get("data", []))
            all_jobs.extend(jobs)

            pagination = data.get("pagination", {})
            if not total:
                total = pagination.get("total", 0)

            offset += limit

            if max_jobs > 0 and len(all_jobs) >= max_jobs:
                all_jobs = all_jobs[:max_jobs]
                break
            if total and offset >= total:
                break
            if not jobs:
                break

        first_response = first_response or response
        return SearchResult(query=query, search_url=search_url, response=first_response, jobs=all_jobs)

    def fetch_job_details(self, bridge_url: str, job: JobSummary, search_url: str, timeout: float) -> tuple[JobDetails, HttpResponse]:
        if not job.external_id:
            raise RuntimeError("job_id ausente")
        response = self.http_client.get(
            bridge_url,
            f"{GUPY_BASE_URL}/{job.external_id}",
            timeout,
            headers=GUPY_HEADERS,
            max_retry=0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"status HTTP inesperado: {response.status_code}")
        data = json.loads(response.text)
        job_data = data if isinstance(data, dict) else {}
        return self._parse_job_detail(job_data), response

    def _parse_jobs(self, data: list[dict]) -> list[JobSummary]:
        jobs: list[JobSummary] = []
        for item in data:
            try:
                jobs.append(JobSummary(
                    provider=self.name,
                    external_id=str(item.get("id", "")),
                    title=item.get("name", ""),
                    company=item.get("careerPageName", ""),
                    location=self._format_location(item.get("city", ""), item.get("state", "")),
                    listed_at=item.get("publishedDate", ""),
                    listed_text="",
                    url=item.get("jobUrl", ""),
                    company_url=item.get("careerPageUrl", ""),
                    logo_url=item.get("careerPageLogo", ""),
                    provider_data={
                        "city": item.get("city", ""),
                        "state": item.get("state", ""),
                        "country": item.get("country", ""),
                        "workplaceType": item.get("workplaceType", ""),
                        "type": item.get("type", ""),
                        "isRemoteWork": item.get("isRemoteWork", False),
                        "disabilities": item.get("disabilities", False),
                        "badges": item.get("badges", {}),
                        "companyId": item.get("companyId"),
                        "careerPageId": item.get("careerPageId"),
                        "publishedDate": item.get("publishedDate", ""),
                        "applicationDeadline": item.get("applicationDeadline", ""),
                    },
                ))
            except ValueError:
                continue
        return jobs

    def _parse_job_detail(self, data: dict) -> JobDetails:
        city = data.get("city", "") or "REMOTO"
        state = data.get("state", "") or ""
        description = data.get("description", "")
        description = description.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")

        return JobDetails(
            title=data.get("name", ""),
            company=data.get("careerPageName", ""),
            company_url=data.get("careerPageUrl", ""),
            location=self._format_location(city, state),
            posted_text=data.get("publishedDate", ""),
            applicants_text="",
            description=description,
            criteria={
                "Tipo": self._type_label(data.get("type", "")),
                "Cidade": city,
                "Estado": state,
                "Trabalho": self._workplace_label(data.get("workplaceType", "")),
                "Remoto": "Sim" if data.get("isRemoteWork") else "Nao",
                "PCD": "Sim" if data.get("disabilities") else "Nao",
                "Prazo": data.get("applicationDeadline", ""),
                "Nivel de experiencia": "N/A",
                "Funcao": "N/A",
                "Setores": "N/A",
                "Salario": "N/A",
                "requisitos": extract_requisitos(description),
            },
            apply_text="",
            url=data.get("jobUrl", ""),
            logo_url=data.get("careerPageLogo", ""),
            provider_data={
                "id": data.get("id"),
                "companyId": data.get("companyId"),
                "publishedDate": data.get("publishedDate", ""),
                "applicationDeadline": data.get("applicationDeadline", ""),
                "badges": data.get("badges", {}),
            },
        )

    @staticmethod
    def _parse_location(query: SearchQuery) -> tuple[str, str]:
        state = ""
        city = ""
        if query.location_id and "|" in query.location_id:
            parts = query.location_id.split("|", 1)
            state = parts[0]
            city = parts[1]
        elif query.location_id == "BR":
            pass
        elif query.location and query.location.lower() not in ("", "brasil", "brasil (todas as localidades)"):
            state = query.location
        return state, city

    @staticmethod
    def _format_location(city: str, state: str) -> str:
        if city and state:
            return f"{city}, {state}"
        if city or state:
            return city or state
        return "REMOTO"

    @staticmethod
    def _type_label(t: str) -> str:
        labels = {
            "vacancy_type_effective": "Efetivo/CLT",
            "vacancy_type_temporary": "Temporário",
            "vacancy_type_internship": "Estágio",
            "vacancy_type_trainee": "Trainee",
            "vacancy_type_young_apprentice": "Jovem Aprendiz",
        }
        return labels.get(t, t)

    @staticmethod
    def _workplace_label(w: str) -> str:
        labels = {
            "remote": "Remoto",
            "hybrid": "Hibrido",
            "on-site": "Presencial",
        }
        return labels.get(w, w)
