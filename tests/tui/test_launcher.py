from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_search.interfaces.launcher import main


class TestLauncher:
    def test_no_args_opens_tui(self):
        app = MagicMock()
        app.run.return_value = 0

        with patch("job_search.interfaces.launcher.TuiApp", return_value=app):
            result = main([])

        assert result == 0
        app.run.assert_called_once_with()

    def test_args_delegate_to_cli(self):
        with patch("job_search.interfaces.launcher.cli_main", return_value=0) as cli_main:
            result = main(["--portal", "linkedin"])

        assert result == 0
        cli_main.assert_called_once_with(["--portal", "linkedin"])
