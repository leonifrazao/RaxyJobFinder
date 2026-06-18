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
    && rm -rf /var/lib/apt/lists/*

COPY --from=xray /opt/xray /opt/xray
ENV XRAY_PATH=/opt/xray/xray

WORKDIR /app

COPY proxy_framework proxy_framework
RUN pip install --no-cache-dir /app/proxy_framework

COPY buscador_vagas buscador_vagas
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/proxy_framework:/app/buscador_vagas

WORKDIR /app/buscador_vagas
ENTRYPOINT ["python", "buscador.py"]
