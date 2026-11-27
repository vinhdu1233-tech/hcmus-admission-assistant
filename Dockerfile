FROM node:22-bookworm-slim AS node
FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY requirements-backend.txt ./
RUN pip install --no-cache-dir -r requirements-backend.txt
COPY . .
ENV HCMUS_DB_PATH=/data/admissions.sqlite3 HCMUS_PRODUCT_DB_PATH=/data/product.sqlite3 CHAT_MODE=api API_ORIGIN=http://127.0.0.1:8000 PORT=8080 PYTHONUNBUFFERED=1
RUN mkdir -p /data && useradd --uid 10001 --create-home guide && chown -R guide:guide /data /app
USER guide
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=4s --start-period=30s CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/config',timeout=3))['mode']=='api'; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3))['status']=='ok'"
CMD ["python","-m","scripts.run_product"]
