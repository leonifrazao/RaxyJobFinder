{ pkgs ? import <nixpkgs> {} }:

let
  python = pkgs.python3.withPackages (ps: with ps; [
    pip
    requests
    urllib3
    rich
  ]);

  xrayPackages =
    pkgs.lib.optionals (pkgs ? xray) [ pkgs.xray ]
    ++ pkgs.lib.optionals (pkgs ? v2ray) [ pkgs.v2ray ];
in
pkgs.mkShell {
  packages = [
    python
    pkgs.stdenv.cc.cc.lib
  ] ++ xrayPackages;

  shellHook = ''
    export PYTHONPATH="$PWD/proxy_framework/src:$PWD/buscador_vagas:$PYTHONPATH"
    export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"

    if [ ! -d "$PWD/.venv" ]; then
      python -m venv "$PWD/.venv" --system-site-packages
    fi

    export VIRTUAL_ENV="$PWD/.venv"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
    VENV_PYTHON="$VIRTUAL_ENV/bin/python"

    "$VENV_PYTHON" - <<'PY' >/dev/null 2>&1 || "$VENV_PYTHON" -m pip install --upgrade botasaurus dependency-injector beautifulsoup4 pytermgui PyYAML loguru
import botasaurus
import dependency_injector
import bs4
import pytermgui
import yaml
import loguru
PY

    if command -v xray >/dev/null 2>&1; then
      export XRAY_PATH="$(command -v xray)"
    elif command -v v2ray >/dev/null 2>&1; then
      export XRAY_PATH="$(command -v v2ray)"
    fi

    echo "Scrapper LinkedIn nix-shell"
    echo "Python: $("$VENV_PYTHON" --version)"
    echo "Botasaurus: $("$VENV_PYTHON" - <<'PY'
import botasaurus
print(getattr(botasaurus, '__version__', 'installed'))
PY
)"
    echo "Dependency Injector: $("$VENV_PYTHON" - <<'PY'
import dependency_injector
print(getattr(dependency_injector, '__version__', 'installed'))
PY
)"
    echo "PyTermGUI: $("$VENV_PYTHON" - <<'PY'
import pytermgui
print(getattr(pytermgui, '__version__', 'installed'))
PY
)"
    echo "Loguru: $("$VENV_PYTHON" - <<'PY'
import loguru
print(getattr(loguru, '__version__', 'installed'))
PY
)"
    if [ -n "$XRAY_PATH" ]; then
      echo "Xray/V2Ray: $XRAY_PATH"
    else
      echo "Aviso: xray/v2ray nao encontrado. Configure XRAY_PATH manualmente."
    fi
  '';
}
