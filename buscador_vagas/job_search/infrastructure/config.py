import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_type_hints


@dataclass
class DefaultsConfig:
    portal: str = "linkedin"
    keywords: str = "Vagas"
    location: str = "Brasil"
    valid_count: int = 25
    jobs_per_proxy: int = 5
    max_count: int = 177
    threads: int = 8
    timeout: float = 12.0
    detail_timeout: float = 15.0
    details_limit: int = 0
    start: int = 0
    max_jobs: int = 0
    detail_threads: int = 5
    show_jobs: int = 10
    silent: bool = True
    gd_cookie: str = ""
    filters_path: str = ""
    location_id: str = ""
    location_choice: str = "1"
    work_type: str = "normal"
    under_10_applicants: bool = False


@dataclass
class OutputConfig:
    jobs_path: str = "output/{portal}/vagas.json"
    details_path: str = "output/{portal}/detalhadas.json"


@dataclass
class ProxyProvidersConfig:
    united_states: str = ""
    brazil: str = ""
    canada: str = ""
    germany: str = ""
    netherlands: str = ""
    all: str = ""


@dataclass
class ProxyConfig:
    detection_timeout: float = 3.0
    default_provider: str = "united-states"
    providers: ProxyProvidersConfig = field(default_factory=ProxyProvidersConfig)
    all_countries: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class RedisConfig:
    url: str = "redis://localhost:6379/0"
    channel: str = "raxy:events"
    data_channel: str = "vagas:disponiveis"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    path: str = "logs/raxy.jsonl"
    error_path: str = "logs/raxy-error.log"


@dataclass
class TuiConfig:
    title: str = "Raxy Job Finder"


@dataclass
class RaxySettings:
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    portals: tuple[str, ...] = ("linkedin", "gupy", "glassdoor")
    tui: TuiConfig = field(default_factory=TuiConfig)


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _dasherize_keys(data: Any) -> Any:
    if isinstance(data, dict):
        return {k.replace("-", "_"): _dasherize_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_dasherize_keys(v) for v in data]
    return data


def _from_dict(cls: type, data: dict) -> Any:
    import dataclasses
    hints = get_type_hints(cls)
    field_names = {f.name for f in dataclasses.fields(cls)}
    kwargs = {}
    for key, value in data.items():
        if key not in field_names:
            continue
        field_type = hints[key]
        origin = getattr(field_type, "__origin__", None)
        args = getattr(field_type, "__args__", None)
        if hasattr(field_type, "__dataclass_fields__"):
            kwargs[key] = _from_dict(field_type, value)
        elif origin is tuple and args:
            kwargs[key] = tuple(value)
        else:
            kwargs[key] = value
    return cls(**kwargs)


def _load_config_from_yaml(path: str | Path) -> dict:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _validate_yaml_config(data: dict) -> None:
    defaults = data.get("defaults")
    if isinstance(defaults, dict) and "keywords" in defaults:
        raise ValueError(
            "defaults.keywords nao e aceito em config.yaml; "
            "informe o termo de busca na CLI, SDK ou TUI."
        )


def _apply_env_overrides(data: dict) -> dict:
    env_map = {
        "RAXY_LOG_LEVEL": ("logging", "level"),
        "RAXY_LOG_PATH": ("logging", "path"),
        "RAXY_ERROR_LOG_PATH": ("logging", "error_path"),
        "RAXY_REDIS_URL": ("redis", "url"),
        "RAXY_REDIS_CHANNEL": ("redis", "channel"),
        "RAXY_REDIS_DATA_CHANNEL": ("redis", "data_channel"),
    }
    for env_key, keys in env_map.items():
        value = os.getenv(env_key)
        if value is not None:
            target = data
            for key in keys[:-1]:
                target = target.setdefault(key, {})
            target[keys[-1]] = value
    return data


DEFAULT_YAML_PATHS = [
    Path("config.yaml"),
    Path.home() / ".raxy" / "config.yaml",
    Path("/etc/raxy/config.yaml"),
]


def find_config_path(path: str | None = None) -> Path | None:
    if path:
        p = Path(path)
        if p.exists():
            return p
        return None
    for p in DEFAULT_YAML_PATHS:
        if p.exists():
            return p
    return None


def _find_config(path: str | None = None) -> Path | None:
    return find_config_path(path)


def _yaml_to_flat_dict(data: dict, prefix: str = "") -> dict:
    result = {}
    for key, value in data.items():
        full_key = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_yaml_to_flat_dict(value, f"{full_key}_"))
        else:
            result[full_key] = value
    return result


_settings_instance: RaxySettings | None = None


def load_settings(path: str | None = None, *, reload: bool = False) -> RaxySettings:
    global _settings_instance
    if _settings_instance is not None and not reload:
        return _settings_instance

    base = _default_dict()
    config_path = _find_config(path)
    if config_path:
        yaml_data = _load_config_from_yaml(config_path)
        yaml_data = _dasherize_keys(yaml_data)
        _validate_yaml_config(yaml_data)
        base = _deep_merge(base, yaml_data)

    base = _apply_env_overrides(base)

    settings = _from_dict(RaxySettings, base)
    _apply_proxy_providers(settings)
    _settings_instance = settings
    return settings


def _default_dict() -> dict:
    return {
        "defaults": {
            "portal": "linkedin", "keywords": "Vagas", "location": "Brasil",
            "valid_count": 25, "jobs_per_proxy": 5, "max_count": 177,
            "threads": 8, "timeout": 12.0, "detail_timeout": 15.0,
            "details_limit": 0, "start": 0, "max_jobs": 0,
            "detail_threads": 5, "show_jobs": 10, "silent": True,
            "gd_cookie": "", "filters_path": "", "location_id": "",
            "location_choice": "1", "work_type": "normal", "under_10_applicants": False,
        },
        "output": {
            "jobs_path": "output/{portal}/vagas.json",
            "details_path": "output/{portal}/detalhadas.json",
        },
        "proxy": {
            "detection_timeout": 3.0,
            "default_provider": "united-states",
            "providers": {
                "united_states": "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-country/United_States.txt",
                "brazil": "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-country/Brazil.txt",
                "canada": "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-country/Canada.txt",
                "germany": "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-country/Germany.txt",
                "netherlands": "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-country/Netherlands.txt",
                "all": "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-country",
            },
            "all_countries": [
                "Albania", "Australia", "Bosnia_and_Herzegovina", "Brazil",
                "Bulgaria", "Canada", "Czechia", "Finland", "France",
                "Georgia", "Germany", "Hong_Kong", "Hungary", "India",
                "Ireland", "Israel", "Italy", "Japan", "Latvia", "Malaysia",
                "Moldova", "Netherlands", "Norway", "Philippines", "Poland",
                "Russia", "Serbia", "Singapore", "South_Africa", "South_Korea",
                "Spain", "Sweden", "Switzerland", "Taiwan", "Thailand",
                "Turkey", "United_Arab_Emirates", "United_Kingdom",
                "United_States", "Unknown",
            ],
        },
        "redis": {
            "url": "redis://localhost:6379/0",
            "channel": "raxy:events",
            "data_channel": "vagas:disponiveis",
        },
        "logging": {
            "level": "INFO",
            "path": "logs/raxy.jsonl",
            "error_path": "logs/raxy-error.log",
        },
        "portals": ["linkedin", "gupy", "glassdoor"],
        "tui": {
            "title": "Raxy Job Finder",
        },
    }


def _apply_proxy_providers(settings: RaxySettings) -> None:
    pc = settings.proxy.providers
    base_url = getattr(pc, "all", "")
    if base_url and settings.proxy.all_countries:
        pc.all = [f"{base_url}/{country}.txt" for country in settings.proxy.all_countries]


def resolve_proxy_sources(provider_name: str, custom_sources: list[str] | None = None) -> list[str]:
    if custom_sources is not None:
        return custom_sources
    settings = load_settings()
    pc = settings.proxy
    provider_key = provider_name.replace("-", "_")
    provider_sources = getattr(pc.providers, provider_key, None)
    if provider_sources is None:
        provider_key = pc.default_provider.replace("-", "_")
        provider_sources = getattr(pc.providers, provider_key, None)
    if isinstance(provider_sources, list):
        return provider_sources
    if provider_sources:
        return [provider_sources]
    return []


def reset_settings() -> None:
    global _settings_instance
    _settings_instance = None
