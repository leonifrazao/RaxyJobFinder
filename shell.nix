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
    export PYTHONPATH="$PWD/proxy_framework:$PWD/buscador_vagas:$PYTHONPATH"
    export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"

    if [ ! -d "$PWD/.venv" ]; then
      python -m venv "$PWD/.venv" --system-site-packages
    fi

    . "$PWD/.venv/bin/activate"

    python - <<'PY' >/dev/null 2>&1 || python -m pip install --upgrade botasaurus dependency-injector beautifulsoup4
import botasaurus
import dependency_injector
import bs4
PY

    if command -v xray >/dev/null 2>&1; then
      export XRAY_PATH="$(command -v xray)"
    elif command -v v2ray >/dev/null 2>&1; then
      export XRAY_PATH="$(command -v v2ray)"
    fi

    echo "Scrapper LinkedIn nix-shell"
    echo "Python: $(python --version)"
    echo "Botasaurus: $(python - <<'PY'
import botasaurus
print(getattr(botasaurus, '__version__', 'installed'))
PY
)"
    echo "Dependency Injector: $(python - <<'PY'
import dependency_injector
print(getattr(dependency_injector, '__version__', 'installed'))
PY
)"
    if [ -n "$XRAY_PATH" ]; then
      echo "Xray/V2Ray: $XRAY_PATH"
    else
      echo "Aviso: xray/v2ray nao encontrado. Configure XRAY_PATH manualmente."
    fi
  '';
}
