from __future__ import annotations

from job_search.infrastructure.config import load_settings


def _build_providers_dict():
    settings = load_settings()
    pc = settings.proxy
    providers = {}
    for attr in ["united_states", "brazil", "canada", "germany", "netherlands"]:
        url = getattr(pc.providers, attr, None)
        if url:
            key = attr.replace("_", "-")
            providers[key] = url
    all_sources = pc.providers.all
    if isinstance(all_sources, list):
        providers["all"] = all_sources
    elif all_sources:
        providers["all"] = [all_sources]
    return providers


DEFAULT_PROVIDER = load_settings().proxy.default_provider
PROXY_PROVIDERS = _build_providers_dict()


def resolve_proxy_sources(provider_name: str, custom_sources: list[str] | None = None) -> list[str]:
    if custom_sources is not None:
        return custom_sources
    provider_sources = PROXY_PROVIDERS.get(provider_name, PROXY_PROVIDERS.get(DEFAULT_PROVIDER, []))
    return provider_sources if isinstance(provider_sources, list) else [provider_sources]
