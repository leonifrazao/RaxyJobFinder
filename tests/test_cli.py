from __future__ import annotations

from job_search.infrastructure.proxy.proxy_sources import DEFAULT_PROVIDER, PROXY_PROVIDERS
from job_search.infrastructure.config import load_settings
from job_search.interfaces.cli.command import build_parser


class TestBuildParser:
    def test_default_portal(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.portal == "linkedin"

    def test_default_keywords(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.keywords == "Vagas"

    def test_default_location(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.location == "Brasil"

    def test_default_provider(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.provider == DEFAULT_PROVIDER
        assert args.provider == "united-states"

    def test_default_valid_count(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.valid_count == 25

    def test_default_threads(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.threads == 8

    def test_default_detail_threads(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.detail_threads == 5

    def test_default_timeout(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.timeout == 12.0

    def test_default_detail_timeout(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.detail_timeout == 15.0

    def test_default_show_jobs(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.show_jobs == 10

    def test_default_details_limit(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.details_limit == 0

    def test_default_start(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.start == 0

    def test_default_max_jobs(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.max_jobs == 0

    def test_default_gd_cookie(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.gd_cookie == ""

    def test_portal_choices(self):
        parser = build_parser()
        args = parser.parse_args(["--portal", "gupy"])
        assert args.portal == "gupy"
        args = parser.parse_args(["--portal", "glassdoor"])
        assert args.portal == "glassdoor"

    def test_override_keywords(self):
        parser = build_parser()
        args = parser.parse_args(["--keywords", "Data Science"])
        assert args.keywords == "Data Science"

    def test_override_location(self):
        parser = build_parser()
        args = parser.parse_args(["--location", "São Paulo"])
        assert args.location == "São Paulo"

    def test_location_id(self):
        parser = build_parser()
        args = parser.parse_args(["--location-id", "106057199"])
        assert args.location_id == "106057199"

    def test_geo_id_is_alias(self):
        parser = build_parser()
        args = parser.parse_args(["--geo-id", "106057199"])
        assert args.location_id == "106057199"

    def test_location_choice(self):
        parser = build_parser()
        args = parser.parse_args(["--location-choice", "2"])
        assert args.location_choice == 2

    def test_valid_count(self):
        parser = build_parser()
        args = parser.parse_args(["--valid-count", "10"])
        assert args.valid_count == 10

    def test_jobs_per_proxy(self):
        parser = build_parser()
        args = parser.parse_args(["--jobs-per-proxy", "3"])
        assert args.jobs_per_proxy == 3

    def test_max_count(self):
        parser = build_parser()
        args = parser.parse_args(["--max-count", "50"])
        assert args.max_count == 50

    def test_threads(self):
        parser = build_parser()
        args = parser.parse_args(["--threads", "16"])
        assert args.threads == 16

    def test_detail_threads(self):
        parser = build_parser()
        args = parser.parse_args(["--detail-threads", "10"])
        assert args.detail_threads == 10

    def test_timeout_float(self):
        parser = build_parser()
        args = parser.parse_args(["--timeout", "30.5"])
        assert args.timeout == 30.5

    def test_detail_timeout(self):
        parser = build_parser()
        args = parser.parse_args(["--detail-timeout", "8.0"])
        assert args.detail_timeout == 8.0

    def test_jobs_output(self):
        parser = build_parser()
        args = parser.parse_args(["--jobs-output", "my/jobs.json"])
        assert args.jobs_output == "my/jobs.json"

    def test_details_output(self):
        parser = build_parser()
        args = parser.parse_args(["--details-output", "my/details.json"])
        assert args.details_output == "my/details.json"

    def test_filters(self):
        parser = build_parser()
        args = parser.parse_args(["--filters", "filters/python.json"])
        assert args.filters == "filters/python.json"

    def test_details_limit(self):
        parser = build_parser()
        args = parser.parse_args(["--details-limit", "5"])
        assert args.details_limit == 5

    def test_show_jobs(self):
        parser = build_parser()
        args = parser.parse_args(["--show-jobs", "50"])
        assert args.show_jobs == 50

    def test_proxy_source_multiple(self):
        parser = build_parser()
        args = parser.parse_args(["--proxy-source", "url1", "--proxy-source", "url2"])
        assert args.proxy_source == ["url1", "url2"]

    def test_provider_choices(self):
        parser = build_parser()
        for provider in ["all", "brazil", "united-states"]:
            args = parser.parse_args(["--provider", provider])
            assert args.provider == provider

    def test_start(self):
        parser = build_parser()
        args = parser.parse_args(["--start", "60"])
        assert args.start == 60

    def test_max_jobs(self):
        parser = build_parser()
        args = parser.parse_args(["--start", "0", "--max-jobs", "180"])
        assert args.max_jobs == 180

    def test_gd_cookie(self):
        parser = build_parser()
        args = parser.parse_args(["--gd-cookie", "cookie_string"])
        assert args.gd_cookie == "cookie_string"


class TestProxyProviders:
    def test_default_provider_is_united_states(self):
        assert DEFAULT_PROVIDER == "united-states"

    def test_united_states_url(self):
        url = PROXY_PROVIDERS["united-states"]
        assert url.endswith("/United_States.txt")

    def test_brazil_url(self):
        url = PROXY_PROVIDERS["brazil"]
        assert url.endswith("/Brazil.txt")

    def test_all_is_list(self):
        providers = PROXY_PROVIDERS["all"]
        assert isinstance(providers, list)
        assert len(providers) > 0
        assert all(p.startswith("http") for p in providers)

    def test_all_country_count(self):
        settings = load_settings()
        assert len(settings.proxy.all_countries) == 40
