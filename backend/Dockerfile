FROM python:3.11-slim

WORKDIR /app

# Dependências de sistema necessárias para compilar libs nativas (ex.: psycopg)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_ENV=production
EXPOSE 5000

# 1) aplica as migrações do banco; 2) sobe o gunicorn.
# UM worker (com várias threads) de propósito: o agendador de tarefas
# (lembretes de WhatsApp) roda dentro do processo, e com 2+ workers cada um
# enviaria o mesmo lembrete. A porta vem da variável PORT (Render, Railway...).
CMD ["sh", "-c", "flask --app run.py db upgrade && gunicorn run:app --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 4 --timeout 60"]
