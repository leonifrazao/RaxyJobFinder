# Proxy Framework

Framework independente extraido do proxy do Raxy para carregar, interpretar, testar e expor proxies Xray/V2Ray como bridges HTTP locais.

## Recursos

- Parse de URIs `ss://`, `vmess://`, `vless://` e `trojan://`.
- Leitura de fontes locais ou URLs.
- Teste funcional com bridge temporaria via Xray/V2Ray.
- Cache de resultados em JSON.
- Filtro por pais.
- Start/stop de bridges HTTP locais.

## Requisitos

- Python 3.10+.
- Binario `xray` ou `v2ray` no `PATH`, ou variavel `XRAY_PATH` apontando para o executavel.

## Instalar em modo editavel

```bash
python -m pip install -e ./proxy_framework
```

## Uso basico

```python
from proxy_framework import create_proxy

proxy = create_proxy(
    proxies=["vless://..."],
    use_console=True,
)

results = proxy.test(threads=4, timeout=10)
active = proxy.start(amounts=1, auto_test=False)

print(proxy.get_http_proxy())
proxy.stop()
```

## Uso com fonte externa

```python
from proxy_framework import create_proxy

proxy = create_proxy(sources=["./proxies.txt"])
proxy.test(threads=8, country="BR")
proxy.start(amounts=2, country="BR")
```

## Fonte publica vmess

```python
from proxy_framework import create_proxy

source = "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vmess_configs.txt"

proxy = create_proxy(sources=[source], max_count=200)
results = proxy.test(threads=8, timeout=10, find_first=5, find_first_unique=True)
active = proxy.start(amounts=5, auto_test=False)
print([item.uri for item in active])
```

Tambem ha um exemplo pronto em `examples/use_ebrasha_vmess.py`.

Para testar uma fonte e iniciar 5 proxies funcionais com IP de saida unico:

```bash
nix-shell --run 'python examples/test_ebrasha_request.py --valid-count 5 --max-count 200'
```
