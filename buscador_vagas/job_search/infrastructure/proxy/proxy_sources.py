from __future__ import annotations


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
    "all": [f"{SPLITTED_BY_COUNTRY_BASE}/{country}.txt" for country in ALL_COUNTRY_FILES],
}
DEFAULT_PROVIDER = "united-states"


def resolve_proxy_sources(provider_name: str, custom_sources: list[str] | None = None) -> list[str]:
    if custom_sources is not None:
        return custom_sources
    provider_sources = PROXY_PROVIDERS.get(provider_name, PROXY_PROVIDERS[DEFAULT_PROVIDER])
    return provider_sources if isinstance(provider_sources, list) else [provider_sources]
