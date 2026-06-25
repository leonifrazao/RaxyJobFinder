from __future__ import annotations

import json
import re
from urllib.parse import urlencode, quote

from job_search.application.dto.output.http_response import HttpResponse
from job_search.application.dto.output.search_result import SearchResult
from job_search.application.ports.http_client import HttpClient
from job_search.domain.job_details import JobDetails, extract_requisitos
from job_search.domain.job_summary import JobSummary
from job_search.domain.location_option import LocationOption
from job_search.domain.search_query import SearchQuery
from job_search.infrastructure.config import load_settings


GLASSDOOR_BASE = "https://www.glassdoor.com.br"
GLASSDOOR_JOB_SEARCH_URL = f"{GLASSDOOR_BASE}/job-search-next/bff/jobSearchResultsQuery"
GLASSDOOR_LOCATION_URL = f"{GLASSDOOR_BASE}/autocomplete/location"
GLASSDOOR_JOB_DETAILS_URL = f"{GLASSDOOR_BASE}/job-listing/api/job-details"

GLASSDOOR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0",
    "Accept": "*/*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": f"{GLASSDOOR_BASE}/",
    "Origin": GLASSDOOR_BASE,
    "DNT": "1",
    "Sec-GPC": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


class GlassdoorJobBoardAdapter:
    name = "glassdoor"

    # Maps Glassdoor typeahead kind tokens to search API locationType values
    _LOCATION_TYPE_MAP = {
        "C": "CITY",
        "S": "STATE",
        "N": "COUNTRY",
    }

    def __init__(self, http_client: HttpClient, cookie_string: str = "") -> None:
        self.http_client = http_client
        self._cookie_string = cookie_string

    def _ensure_cookies(self, bridge_url: str, timeout: float) -> None:
        if self._cookie_string:
            return
        try:
            resp = self.http_client.get(bridge_url, GLASSDOOR_BASE, timeout, headers=GLASSDOOR_HEADERS, max_retry=0)
            self._update_cookies(resp)
        except Exception:
            pass

    def _update_cookies(self, resp: HttpResponse) -> None:
        if not resp.cookies:
            return
        parts = []
        for name, value in resp.cookies.items():
            escaped_value = value.replace(",", "%2C").replace(";", "%3B")
            parts.append(f"{name}={escaped_value}")
        new_cookies = "; ".join(parts)
        if new_cookies:
            if self._cookie_string:
                self._cookie_string = self._cookie_string.rstrip("; ") + "; " + new_cookies
            else:
                self._cookie_string = new_cookies

    def _headers(self) -> dict[str, str]:
        h = dict(GLASSDOOR_HEADERS)
        if self._cookie_string:
            h["Cookie"] = self._cookie_string
        return h

    def build_search_url(self, query: SearchQuery) -> str:
        keyword_slug = _slugify(query.keywords) if query.keywords else "vagas"
        loc_part = ""
        if query.location_id:
            parts = query.location_id.split("|", 1)
            loc_id = parts[0]
            loc_type = self._LOCATION_TYPE_MAP.get(parts[1], "") if len(parts) > 1 else ""
            if loc_type in ("CITY", "STATE"):
                loc_part = f"-SRCH_IL.0,{len(query.location)}_IC{loc_id}"
        elif query.location:
            loc_part = f"-SRCH_IL.0,{len(query.location)}"
        return f"{GLASSDOOR_BASE}/Vaga/{keyword_slug}-vagas{loc_part}_KO0,{len(query.keywords) or 0}.htm"

    def get_location_options(self, bridge_url: str, location_query: str, timeout: float) -> list[LocationOption]:
        url = f"{GLASSDOOR_LOCATION_URL}?locationTypeFilters=CITY,STATE,COUNTRY&caller=jobs&term={quote(location_query)}"
        resp = self.http_client.get(bridge_url, url, timeout, headers=self._headers())
        self._update_cookies(resp)
        data = json.loads(resp.text)
        return [
            LocationOption(
                id=f"{item['locationId']}|{item.get('locationType', '')}",
                name=item.get("locationName", ""),
                kind=item.get("locationType", ""),
                provider=self.name,
                raw=item,
            )
            for item in data
            if isinstance(item, dict) and item.get("locationId")
        ]

    def search_jobs(self, bridge_url: str, query: SearchQuery, timeout: float, *, max_jobs: int = 0, start: int = 0) -> SearchResult:
        self._ensure_cookies(bridge_url, timeout)
        search_url = self.build_search_url(query)
        all_jobs: list[JobSummary] = []
        page_number = 1
        page_cursor = ""
        first_response = None
        total = 0

        body: dict = {
            "excludeJobListingIds": [],
            "filterParams": [],
            "includeIndeedJobAttributes": True,
            "keyword": query.keywords,
            "numJobsToShow": 100,
            "pageCursor": "",
            "pageNumber": page_number,
            "pageType": "SERP",
        }

        if query.location_id:
            parts = query.location_id.split("|", 1)
            loc_id = parts[0]
            loc_type = self._LOCATION_TYPE_MAP.get(parts[1], "") if len(parts) > 1 else ""
            if loc_type in ("CITY", "STATE"):
                body["locationId"] = int(loc_id) if loc_id.isdigit() else loc_id
                body["locationType"] = loc_type

        while True:
            body["pageCursor"] = page_cursor
            body["pageNumber"] = page_number

            resp = self.http_client.post(bridge_url, GLASSDOOR_JOB_SEARCH_URL, timeout, json_body=body, headers=self._headers())
            self._update_cookies(resp)
            if first_response is None:
                first_response = resp

            if resp.status_code != 200:
                raise RuntimeError(f"status HTTP inesperado: {resp.status_code}")

            data = json.loads(resp.text)
            errors = data.get("errors")
            if errors:
                raise RuntimeError(f"Glassdoor API error: {errors[0].get('message', str(errors[0]))}")

            result = data.get("data", {}).get("jobListings", {})
            listings = result.get("jobListings", [])
            jobs = self._parse_jobs(listings)
            all_jobs.extend(jobs)

            if not total:
                total = result.get("totalJobsCount", 0)

            cursors = result.get("paginationCursors", [])
            next_cursor = None
            for c in cursors:
                if c.get("pageNumber") == page_number + 1:
                    next_cursor = c.get("cursor", "")
                    break

            page_number += 1
            page_cursor = next_cursor or ""

            if max_jobs > 0 and len(all_jobs) >= max_jobs:
                all_jobs = all_jobs[:max_jobs]
                break
            if not jobs or not next_cursor:
                break
            if total and len(all_jobs) >= total:
                break

        first_response = first_response or resp
        return SearchResult(query=query, search_url=search_url, response=first_response, jobs=all_jobs)

    def fetch_job_details(self, bridge_url: str, job: JobSummary, search_url: str, timeout: float) -> tuple[JobDetails, HttpResponse]:
        self._ensure_cookies(bridge_url, timeout)
        job_link = job.provider_data.get("jobLink", "")
        job_listing_id = job.external_id

        params: dict[str, str] = {
            "jobListingId": job_listing_id,
            "pageTypeEnum": "SERP",
            "countryId": "36",
        }
        if job_link:
            params["queryString"] = job_link

        url = f"{GLASSDOOR_JOB_DETAILS_URL}?{urlencode(params)}"
        resp = self.http_client.get(bridge_url, url, timeout, headers=self._headers(), max_retry=0)
        self._update_cookies(resp)

        details = self._build_details_from_summary(job)
        if resp.status_code == 200 and resp.text:
            try:
                data = json.loads(resp.text)
                if "data" in data:
                    details = self._enrich_details(details, data["data"])
                elif "error" not in data:
                    details = self._enrich_details(details, data)
            except (json.JSONDecodeError, ValueError):
                pass

        return details, resp

    def _parse_jobs(self, listings: list[dict]) -> list[JobSummary]:
        jobs: list[JobSummary] = []
        for item in listings:
            try:
                jv = item.get("jobview", item)
                header = jv.get("header", {})
                job_info = jv.get("job", {})
                overview = jv.get("overview", {})

                employer = header.get("employer", {})
                listing_id = str(job_info.get("listingId", header.get("adOrderId", "")))
                title = header.get("jobTitleText", "")
                company = employer.get("name", header.get("employerNameFromSearch", ""))
                location = header.get("locationName", "")
                published_date = ""
                # ageInDays is available but not absolute date
                logo_url = overview.get("squareLogoUrl", "")
                seo_link = header.get("seoJobLink", "")
                job_link = header.get("jobLink", "")

                jobs.append(JobSummary(
                    provider=self.name,
                    external_id=listing_id,
                    title=title,
                    company=company,
                    location=location,
                    listed_at=published_date,
                    listed_text=f"{header.get('ageInDays', '')} dias atras" if header.get("ageInDays") else "",
                    url=seo_link,
                    company_url="",
                    logo_url=logo_url,
                    provider_data={
                        "jobLink": job_link,
                        "listingId": listing_id,
                        "jobResultTrackingKey": header.get("jobResultTrackingKey", ""),
                        "locId": header.get("locId", ""),
                        "locationType": header.get("locationType", ""),
                        "goc": header.get("goc", ""),
                        "gocId": header.get("gocId", ""),
                        "employerId": employer.get("id", ""),
                        "easyApply": header.get("easyApply", False),
                        "isSponsoredJob": header.get("isSponsoredJob", False),
                        "ageInDays": header.get("ageInDays", 0),
                        "payCurrency": header.get("payCurrency", ""),
                        "salarySource": header.get("salarySource", ""),
                    },
                ))
            except ValueError:
                continue
        return jobs

    def _build_details_from_summary(self, job: JobSummary) -> JobDetails:
        city = ""
        state = ""
        loc = job.location
        if loc and "," in loc:
            parts = loc.split(",", 1)
            city = parts[0].strip()
            state = parts[1].strip()

        return JobDetails(
            title=job.title,
            company=job.company,
            company_url="",
            location=job.location,
            posted_text=job.listed_text,
            applicants_text="",
            description="",
            criteria={
                "Tipo": "N/A",
                "Cidade": city,
                "Estado": state,
                "Trabalho": "N/A",
                "Remoto": "N/A",
                "PCD": "N/A",
                "Prazo": "N/A",
                "Nivel de experiencia": "N/A",
                "Funcao": "N/A",
                "Setores": "N/A",
                "Salario": "N/A",
                "Easy Apply": "Sim" if job.provider_data.get("easyApply") else "Nao",
            },
            url=job.url,
            logo_url=job.logo_url,
            provider_data=dict(job.provider_data),
        )

    def _enrich_details(self, details: JobDetails, data: dict) -> JobDetails:
        jv = data.get("jobview", data)
        header = jv.get("header", {})
        job_info = jv.get("job", {})
        employer = header.get("employer", {})

        desc = job_info.get("description", "")
        if not desc:
            frags = job_info.get("descriptionFragments", [])
            if frags:
                desc = " ".join(f.get("text", "") for f in frags if isinstance(f, dict))
        if not desc:
            desc_text = job_info.get("descriptionFragmentsText", "")
            if isinstance(desc_text, list):
                desc = " ".join(str(d) for d in desc_text)
            elif isinstance(desc_text, str):
                desc = desc_text

        location = header.get("locationName", details.location)
        city = ""
        state = ""
        if location and "," in location:
            parts = location.split(",", 1)
            city = parts[0].strip()
            state = parts[1].strip()

        criteria = dict(details.criteria)
        if header.get("goc"):
            criteria["Funcao"] = header.get("goc", "")
        if header.get("salarySource"):
            criteria["Salario"] = f"{header.get('payCurrency', '')} ({header.get('salarySource', '')})"
        criteria["Cidade"] = city
        criteria["Estado"] = state
        criteria["Easy Apply"] = "Sim" if header.get("easyApply") else "Nao"
        criteria["requisitos"] = extract_requisitos(
            desc,
            load_settings().requirement_extraction.patterns,
        )

        return JobDetails(
            title=header.get("jobTitleText", details.title),
            company=employer.get("name", details.company),
            company_url="",
            location=location,
            posted_text=details.posted_text,
            applicants_text="",
            description=desc,
            criteria=criteria,
            url=header.get("seoJobLink", details.url),
            logo_url=details.logo_url,
            provider_data=details.provider_data,
        )
