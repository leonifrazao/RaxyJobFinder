# Stage 1 - Xray
FROM python:3.13-slim AS xray

ARG XRAY_VERSION=1.8.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ca-certificates \
    && curl -fsSL \
    "https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-linux-64.zip" \
    -o /tmp/xray.zip \
    && unzip /tmp/xray.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/xray \
    && rm /tmp/xray.zip \
    && apt-get purge -y curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Stage 2 - App
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Xray
COPY --from=xray /usr/local/bin/xray /usr/local/bin/xray
ENV XRAY_PATH=/usr/local/bin/xray

WORKDIR /app

# Proxy framework / SDK
COPY proxy_framework /app/proxy_framework
RUN pip install --no-cache-dir /app/proxy_framework

# API requirements
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt

COPY . /app

# Instala projeto principal
RUN pip install --no-cache-dir -e .

RUN python -c "import urllib.request, os; \
url='https://github.com/daijro/hrequests/releases/download/v0.8.0-beta.2/hrequests-cgo-2.0-linux-amd64.so'; \
dest='/usr/local/lib/python3.13/site-packages/botasaurus_requests/bin/hrequests-cgo-2.0-linux-amd64.so'; \
os.makedirs(os.path.dirname(dest), exist_ok=True); \
urllib.request.urlretrieve(url, dest)"

ENV PYTHONPATH=/app/proxy_framework:/app
ENV OUTPUT_PATH=/app/output

RUN mkdir -p /app/output

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]