FROM python:3.11-slim

WORKDIR /app

# Dependências de sistema necessárias para compilar libs nativas (ex.: psycopg)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["sh", "-c", "flask db upgrade && python run.py"]
