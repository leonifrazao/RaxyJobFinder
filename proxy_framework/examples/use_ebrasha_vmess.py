from __future__ import annotations

from src import create_proxy


VMESS_SOURCE = "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vmess_configs.txt"


def main() -> None:
    proxy = create_proxy(
        sources=[VMESS_SOURCE],
        max_count=5,
        use_console=True,
    )

    print(f"Carregadas: {len(proxy.entries)}")
    print(f"Erros de parse: {len(proxy.parse_errors)}")

    # Descomente para testar conectividade real. Requer xray/v2ray instalado.
    # results = proxy.test(threads=8, timeout=10, find_first=3)
    # active = proxy.start(amounts=1, auto_test=False)
    # print(proxy.get_http_proxy())
    # proxy.stop()


if __name__ == "__main__":
    main()
