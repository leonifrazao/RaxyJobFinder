from __future__ import annotations

import argparse
import sys

import requests

from proxy_framework import create_proxy


DEFAULT_SOURCE = "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vmess_configs.txt"


def proxy_ip_key(entry) -> str | None:
    return entry.result.proxy_ip or entry.result.external_ip or entry.result.ip


def keep_unique_working_proxies(results) -> list:
    working = [entry for entry in results if entry.result.status == "OK"]
    working.sort(key=lambda entry: entry.result.ping_ms if entry.result.ping_ms is not None else float("inf"))

    seen_ips: set[str] = set()
    unique = []
    for entry in working:
        ip_key = proxy_ip_key(entry)
        if not ip_key:
            entry.result.status = "FILTRADO"
            entry.result.error = "Proxy funcional sem IP de saida identificavel"
            continue
        if ip_key in seen_ips:
            entry.result.status = "FILTRADO"
            entry.result.error = f"IP de saida duplicado: {ip_key}"
            continue
        seen_ips.add(ip_key)
        unique.append(entry)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description="Testa um request real usando uma fonte publica de proxies.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="URL ou arquivo local com configs de proxy")
    parser.add_argument("--valid-count", type=int, default=5, help="quantidade de proxies funcionais para encontrar e iniciar")
    parser.add_argument("--max-count", type=int, default=200, help="quantidade maxima de configs para carregar e testar")
    parser.add_argument("--threads", type=int, default=4, help="workers para testar proxies")
    parser.add_argument("--timeout", type=float, default=10.0, help="timeout dos testes em segundos")
    parser.add_argument("--request-url", default="http://httpbin.org/ip", help="URL final para testar via proxy")
    args = parser.parse_args()

    proxy = create_proxy(
        sources=[args.source],
        max_count=args.max_count,
        use_cache=False,
        use_console=True,
    )

    print(f"Carregadas: {len(proxy.entries)}")
    print(f"Erros de parse: {len(proxy.parse_errors)}")

    results = proxy.test(
        threads=args.threads,
        timeout=args.timeout,
        force=True,
        find_first=args.valid_count,
        find_first_unique=True,
    )
    unique_working = keep_unique_working_proxies(results)
    print(f"Proxies funcionais com IP unico: {len(unique_working)}")
    if len(unique_working) < args.valid_count:
        print(
            f"Encontradas apenas {len(unique_working)} proxies funcionais com IP unico de {args.valid_count} solicitadas.",
            file=sys.stderr,
        )
        return 1

    active = proxy.start(amounts=args.valid_count, auto_test=False)
    if not active:
        print("Nao foi possivel iniciar bridge HTTP local.", file=sys.stderr)
        return 1

    try:
        seen_origins: set[str] = set()
        for idx, item in enumerate(active):
            bridge_url = item.uri
            response = requests.get(
                args.request_url,
                proxies={"http": bridge_url, "https": bridge_url},
                timeout=args.timeout,
                verify=False,
            )
            response.raise_for_status()
            origin = response.json().get("origin") if response.headers.get("content-type", "").startswith("application/json") else None
            if isinstance(origin, str) and origin in seen_origins:
                print(f"Bridge {idx} retornou IP duplicado no request final: {origin}", file=sys.stderr)
                return 1
            if isinstance(origin, str):
                seen_origins.add(origin)
            print(f"Bridge {idx}: {bridge_url}")
            print(f"Status: {response.status_code}")
            print(response.text[:500])
        return 0
    finally:
        proxy.stop()


if __name__ == "__main__":
    raise SystemExit(main())
