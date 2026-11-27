FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends nodejs ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-backend.txt ./
RUN pip install --no-cache-dir -r requirements-backend.txt
COPY . .
ENV HCMUS_DB_PATH=/data/admissions.sqlite3 HCMUS_PRODUCT_DB_PATH=/data/product.sqlite3 CHAT_MODE=api API_ORIGIN=http://127.0.0.1:8000 PORT=8080 PYTHONUNBUFFERED=1
RUN mkdir -p /data && useradd --uid 10001 --create-home guide && chown -R guide:guide /data /app
USER guide
EXPOSE 8080
CMD ["python","-m","scripts.run_product"]
