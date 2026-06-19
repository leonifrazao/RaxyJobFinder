from __future__ import annotations

import sys

from job_search.interfaces.cli import main as cli_main
from job_search.interfaces.tui import TuiApp


def main(argv: list[str] | None = None) -> int:
    effective_argv = sys.argv[1:] if argv is None else argv
    if effective_argv:
        return cli_main(effective_argv)
    return TuiApp().run()
