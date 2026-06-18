{ pkgs ? import <nixpkgs> {} }:

let
  python = pkgs.python3.withPackages (ps: with ps; [
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
  ] ++ xrayPackages;

  shellHook = ''
    export PYTHONPATH="$PWD:$PYTHONPATH"

    if command -v xray >/dev/null 2>&1; then
      export XRAY_PATH="$(command -v xray)"
    elif command -v v2ray >/dev/null 2>&1; then
      export XRAY_PATH="$(command -v v2ray)"
    fi

    echo "Proxy Framework nix-shell"
    echo "Python: $(python --version)"
    if [ -n "$XRAY_PATH" ]; then
      echo "Xray/V2Ray: $XRAY_PATH"
    else
      echo "Aviso: xray/v2ray nao encontrado no nixpkgs atual. Configure XRAY_PATH manualmente."
    fi
  '';
}
