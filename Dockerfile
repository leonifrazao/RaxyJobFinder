FROM python:3.13-slim AS xray

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip -o /tmp/xray.zip \
    && unzip /tmp/xray.zip -d /opt/xray \
    && rm /tmp/xray.zip \
    && chmod +x /opt/xray/xray

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        libstdc++6 \
        redis-server \
    && rm -rf /var/lib/apt/lists/*

COPY --from=xray /opt/xray /opt/xray
ENV XRAY_PATH=/opt/xray/xray

WORKDIR /app

COPY proxy_framework proxy_framework
RUN pip install --no-cache-dir /app/proxy_framework

COPY buscador_vagas buscador_vagas
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Pre-download botasaurus native library (hrequests-cgo .so) — bypass GitHub API rate limit
RUN python -c "import urllib.request, os; url='https://github.com/daijro/hrequests/releases/download/v0.8.0-beta.2/hrequests-cgo-2.0-linux-amd64.so'; dest='/usr/local/lib/python3.13/site-packages/botasaurus_requests/bin/hrequests-cgo-2.0-linux-amd64.so'; os.makedirs(os.path.dirname(dest), exist_ok=True); urllib.request.urlretrieve(url, dest); print('Native lib OK:', os.path.getsize(dest), 'bytes')"

ENV PYTHONPATH=/app/proxy_framework:/app/buscador_vagas

RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'redis-server --daemonize yes' >> /entrypoint.sh && \
    echo 'exec python /app/buscador_vagas/buscador.py "$@"' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

WORKDIR /app
ENTRYPOINT ["/entrypoint.sh"]
