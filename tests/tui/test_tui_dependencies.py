from __future__ import annotations


class TestTuiDependencies:
    def test_yaml_loader_dependencies_are_available(self):
        import prompt_toolkit
        import redis
        import yaml

        assert prompt_toolkit.__version__
        assert redis.Redis is not None
        assert yaml.safe_load("enabled: true") == {"enabled": True}
