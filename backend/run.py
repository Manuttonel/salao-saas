# -*- coding: utf-8 -*-
"""
Ponto de entrada do backend. Rodar com:

    python run.py

Isso sobe o servidor de desenvolvimento do Flask em http://localhost:5000.
Para produção, use um servidor WSGI de verdade, ex.:

    gunicorn "run:app" --bind 0.0.0.0:5000
"""

import os

from app import create_app

app = create_app(os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=app.config["DEBUG"])

