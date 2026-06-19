from __future__ import annotations

import json
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from job_search.application.dto.output.http_response import HttpResponse
from job_search.application.dto.output.search_result import SearchResult
from job_search.application.ports.http_client import HttpClient
from job_search.domain.job_details import JobDetails
from job_search.domain.job_summary import JobSummary
from job_search.domain.location_option import LocationOption
from job_search.domain.search_query import SearchQuery


LINKEDIN_SEARCH_BASE_URL = "https://www.linkedin.com/jobs/search"
LINKEDIN_SEE_MORE_API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LINKEDIN_TYPEAHEAD_BASE_URL = "https://www.linkedin.com/jobs-guest/api/typeaheadHits"
LINKEDIN_JOB_POSTING_BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting"
LINKEDIN_REFERER = "https://www.linkedin.com/jobs/search?keywords=Vagas&location=Brasil&geoId=&trk=public_jobs_jobs-search-bar_search-submit&position=1&pageNum=0"

LINKEDIN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Upgrade-Insecure-Requests": "1",
    "Priority": "u=0, i",
    "Alt-Used": "www.linkedin.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-GPC": "1",
}


class LinkedInJobBoardAdapter:
    name = "linkedin"

    def __init__(self, http_client: HttpClient) -> None:
        self.http_client = http_client

    def build_search_url(self, query: SearchQuery) -> str:
        params = {
            "keywords": query.keywords,
            "location": query.location,
            "trk": "public_jobs_jobs-search-bar_search-submit",
        }
        if query.location_id:
            params["geoId"] = query.location_id
        return f"{LINKEDIN_SEARCH_BASE_URL}?{urlencode(params)}"

    def _build_see_more_url(self, query: SearchQuery, offset: int) -> str:
        params = {
            "keywords": query.keywords,
            "location": query.location,
            "trk": "public_jobs_jobs-search-bar_search-submit",
            "start": str(offset),
        }
        if query.location_id:
            params["geoId"] = query.location_id
        return f"{LINKEDIN_SEE_MORE_API_URL}?{urlencode(params)}"

    def get_location_options(self, bridge_url: str, location_query: str, timeout: float) -> list[LocationOption]:
        headers = self._headers(accept="*/*")
        headers["Csrf-Token"] = "ajax:7787813842939664335"
        response = self.http_client.get(
            bridge_url,
            self._typeahead_url(location_query),
            timeout,
            headers=headers,
        )
        text = response.text or "[]"
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Typeahead retornou JSON invalido: {text[:200]}") from exc
        if not isinstance(data, list):
            raise RuntimeError(f"Typeahead retornou formato inesperado: {type(data).__name__}")
        return [
            LocationOption(
                id=str(item.get("id")),
                name=str(item.get("displayName")),
                kind=str(item.get("type") or ""),
                provider=self.name,
                raw=item,
            )
            for item in data
            if isinstance(item, dict) and item.get("id") and item.get("displayName")
        ]

    def search_jobs(self, bridge_url: str, query: SearchQuery, timeout: float, *, max_jobs: int = 0, start: int = 0) -> SearchResult:
        search_url = self.build_search_url(query)
        response = self.http_client.get(bridge_url, search_url, timeout, headers=self._headers())
        if response.status_code != 200:
            raise RuntimeError(f"status HTTP inesperado: {response.status_code}")
        all_jobs = self._parse_jobs_from_html(response.text)

        if max_jobs > 0 and len(all_jobs) < max_jobs:
            step = 60
            offset = max(start, len(all_jobs))
            api_headers = self._api_headers(search_url)
            while len(all_jobs) < max_jobs:
                try:
                    page_resp = self.http_client.get(bridge_url, self._build_see_more_url(query, offset), timeout, headers=api_headers)
                    if page_resp.status_code != 200 or not page_resp.text.strip():
                        break
                    page_jobs = self._parse_jobs_from_api(page_resp.text)
                    if not page_jobs:
                        break
                    existing_ids = {j.external_id for j in all_jobs}
                    new_jobs = [j for j in page_jobs if j.external_id not in existing_ids]
                    if not new_jobs:
                        break
                    all_jobs.extend(new_jobs)
                    offset += step
                except Exception:
                    break
            all_jobs = all_jobs[:max_jobs]

        return SearchResult(query=query, search_url=search_url, response=response, jobs=all_jobs)

    def fetch_job_details(self, bridge_url: str, job: JobSummary, search_url: str, timeout: float) -> tuple[JobDetails, HttpResponse]:
        if not job.external_id:
            raise RuntimeError("job_id ausente")
        headers = self._headers(accept="*/*")
        headers["Referer"] = f"{search_url}&currentJobId={job.external_id}&position={job.provider_data.get('row') or 1}&pageNum=0"
        headers["Csrf-Token"] = "ajax:7787813842939664335"
        response = self.http_client.get(
            bridge_url,
            self._job_posting_url(job.external_id, job.provider_data.get("tracking_id") or None),
            timeout,
            headers=headers,
            max_retry=0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"status HTTP inesperado: {response.status_code}")
        if not response.text.strip():
            raise RuntimeError("HTML de detalhe vazio")
        return self._parse_job_detail_html(response.text), response

    @staticmethod
    def _api_headers(referer: str) -> dict[str, str]:
        headers = dict(LINKEDIN_HEADERS)
        headers["Accept"] = "*/*"
        headers["Referer"] = referer + "&position=1&pageNum=0"
        headers["Csrf-Token"] = "ajax:2280450325479356611"
        return headers

    @staticmethod
    def _typeahead_url(location_query: str) -> str:
        params = {
            "query": location_query,
            "typeaheadType": "GEO",
            "geoTypes": "POPULATED_PLACE,ADMIN_DIVISION_2,MARKET_AREA,COUNTRY_REGION",
        }
        return f"{LINKEDIN_TYPEAHEAD_BASE_URL}?{urlencode(params)}"

    @staticmethod
    def _job_posting_url(job_id: str, tracking_id: str | None = None) -> str:
        url = f"{LINKEDIN_JOB_POSTING_BASE_URL}/{job_id}"
        if tracking_id:
            url = f"{url}?{urlencode({'trackingId': tracking_id})}"
        return url

    @staticmethod
    def _headers(*, accept: str | None = None) -> dict[str, str]:
        headers = dict(LINKEDIN_HEADERS)
        if accept:
            headers["Accept"] = accept
        headers["Referer"] = LINKEDIN_REFERER
        return headers

    def _parse_jobs_from_api(self, text: str) -> list[JobSummary]:
        text = text.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return self._parse_jobs_from_html(text)
            if isinstance(data, dict):
                for key in ("included", "elements", "data"):
                    nested = data.get(key)
                    if nested and isinstance(nested, list):
                        return self._parse_jobs_from_html(json.dumps(nested))
            return []
        return self._parse_jobs_from_html(text)

    def _parse_jobs_from_html(self, html: str) -> list[JobSummary]:
        soup = BeautifulSoup(html, "html.parser")
        results_list = soup.select_one(".jobs-search__results-list")
        if results_list is not None:
            cards = results_list.select(".base-card.job-search-card")
        else:
            cards = soup.select(".base-card.job-search-card")

        jobs: list[JobSummary] = []
        for card in cards:
            entity_urn = card.get("data-entity-urn", "")
            link_element = card.select_one("a.base-card__full-link")
            title_element = card.select_one(".base-search-card__title")
            company_element = card.select_one(".base-search-card__subtitle a") or card.select_one(".base-search-card__subtitle")
            location_element = card.select_one(".job-search-card__location")
            time_element = card.select_one("time.job-search-card__listdate")
            logo_element = card.select_one("img.artdeco-entity-image")

            href = link_element.get("href", "") if link_element else ""
            try:
                jobs.append(JobSummary(
                    provider=self.name,
                    external_id=self._job_id_from_urn(entity_urn),
                    title=self._clean_text(title_element.get_text(" ") if title_element else ""),
                    company=self._clean_text(company_element.get_text(" ") if company_element else ""),
                    location=self._clean_text(location_element.get_text(" ") if location_element else ""),
                    listed_at=time_element.get("datetime", "") if time_element else "",
                    listed_text=self._clean_text(time_element.get_text(" ") if time_element else ""),
                    url=href.replace("&amp;", "&"),
                    company_url=company_element.get("href", "") if company_element and company_element.name == "a" else "",
                    logo_url=logo_element.get("src", "") if logo_element else "",
                    provider_data={
                        "entity_urn": entity_urn,
                        "reference_id": card.get("data-reference-id", ""),
                        "tracking_id": card.get("data-tracking-id", ""),
                        "row": card.get("data-row", ""),
                        "column": card.get("data-column", ""),
                    },
                ))
            except ValueError:
                continue
        return jobs

    def _parse_job_detail_html(self, html: str) -> JobDetails:
        soup = BeautifulSoup(html, "html.parser")
        title_element = soup.select_one(".top-card-layout__title") or soup.select_one(".topcard__title")
        company_element = soup.select_one(".topcard__org-name-link")
        location_element = soup.select_one(".topcard__flavor-row .topcard__flavor--bullet")
        posted_element = soup.select_one(".posted-time-ago__text")
        applicants_element = soup.select_one(".num-applicants__caption")
        description_element = soup.select_one(".description__text .show-more-less-html__markup")
        apply_button = soup.select_one("button.top-card-layout__cta--primary")
        top_link = soup.select_one("a.topcard__link")
        logo_element = soup.select_one(".top-card-layout__card img.artdeco-entity-image")

        criteria: dict[str, str] = {}
        for item in soup.select(".description__job-criteria-item"):
            label_element = item.select_one(".description__job-criteria-subheader")
            value_element = item.select_one(".description__job-criteria-text")
            label = self._clean_text(label_element.get_text(" ") if label_element else "")
            value = self._clean_text(value_element.get_text(" ") if value_element else "")
            if label:
                criteria[label] = value

        decorated_id_code = soup.select_one("#decoratedJobPostingId")
        reference_id_code = soup.select_one("#referenceId")

        return JobDetails(
            title=self._clean_text(title_element.get_text(" ") if title_element else ""),
            company=self._clean_text(company_element.get_text(" ") if company_element else ""),
            company_url=company_element.get("href", "") if company_element else "",
            location=self._clean_text(location_element.get_text(" ") if location_element else ""),
            posted_text=self._clean_text(posted_element.get_text(" ") if posted_element else ""),
            applicants_text=self._clean_text(applicants_element.get_text(" ") if applicants_element else ""),
            description=self._clean_text(description_element.get_text("\n") if description_element else ""),
            criteria=criteria,
            apply_text=self._clean_text(apply_button.get_text(" ") if apply_button else ""),
            url=top_link.get("href", "") if top_link else "",
            logo_url=(logo_element.get("data-delayed-url") or logo_element.get("src") or "") if logo_element else "",
            provider_data={
                "decorated_job_posting_id": self._clean_text(decorated_id_code.get_text(" ") if decorated_id_code else "").strip('"'),
                "detail_reference_id": self._clean_text(reference_id_code.get_text(" ") if reference_id_code else "").strip('"'),
            },
        )

    @staticmethod
    def _clean_text(value: str | None) -> str:
        if not value:
            return ""
        return " ".join(value.split())

    @staticmethod
    def _job_id_from_urn(entity_urn: str) -> str:
        if not entity_urn or ":" not in entity_urn:
            return ""
        return entity_urn.rsplit(":", 1)[-1]
