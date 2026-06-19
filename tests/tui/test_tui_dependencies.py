from __future__ import annotations


class TestTuiDependencies:
    def test_yaml_loader_dependencies_are_available(self):
        import pytermgui as ptg
        import yaml

        assert ptg.YamlLoader is not None
        assert yaml.safe_load("enabled: true") == {"enabled": True}
