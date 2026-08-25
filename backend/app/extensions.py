# -*- coding: utf-8 -*-
"""
Instâncias das extensões Flask usadas em toda a aplicação.

Ficam centralizadas aqui (em vez de dentro de app/__init__.py) para evitar
imports circulares: os models e as rotas importam "db" e "jwt" deste
arquivo, e o create_app() em __init__.py é quem de fato inicializa cada
extensão com "db.init_app(app)".
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()

# O BackgroundScheduler roda em uma thread separada dentro do próprio
# processo Flask. Ele é iniciado em create_app() e os jobs (lembretes,
# verificação de assinaturas) ficam definidos em app/scheduler/jobs.py.
scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
