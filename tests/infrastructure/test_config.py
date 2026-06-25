from __future__ import annotations

import pytest

from job_search.domain.job_details import extract_requisitos
from job_search.infrastructure.config import load_settings, reset_settings


@pytest.fixture(autouse=True)
def reset_config_cache():
    reset_settings()
    yield
    reset_settings()


class TestLoadSettings:
    def test_rejects_keywords_in_yaml_defaults(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text('defaults:\n  keywords: "Python"\n', encoding="utf-8")

        with pytest.raises(ValueError, match="defaults.keywords"):
            load_settings(str(path), reload=True)

    def test_keeps_internal_keyword_default_when_yaml_omits_keywords(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text("defaults:\n  portal: gupy\n", encoding="utf-8")

        settings = load_settings(str(path), reload=True)

        assert settings.defaults.portal == "gupy"
        assert settings.defaults.keywords == "Vagas"

    def test_loads_requirement_patterns_from_yaml(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(
            "requirement_extraction:\n"
            "  patterns:\n"
            "    - pattern: '\\bcurso\\s*superior\\b'\n"
            "      label: ensino_superior\n",
            encoding="utf-8",
        )

        settings = load_settings(str(path), reload=True)

        requisitos = extract_requisitos(
            "Requisitos: Estar matriculado(a) em curso superior.",
            settings.requirement_extraction.patterns,
        )
        assert requisitos == ["ensino_superior"]

    def test_rejects_invalid_requirement_regex(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(
            "requirement_extraction:\n"
            "  patterns:\n"
            "    - pattern: '['\n"
            "      label: invalido\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="pattern invalido"):
            load_settings(str(path), reload=True)
