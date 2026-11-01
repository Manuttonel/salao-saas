# -*- coding: utf-8 -*-
"""
Application factory: monta e configura a aplicação Flask.

Usamos o padrão "create_app()" (em vez de criar o app direto no módulo)
porque isso facilita testes automatizados (cada teste pode criar uma
instância nova do app, com configuração de teste) e evita problemas de
import circular entre extensões, models e rotas.
"""

import logging

from flask import Flask, jsonify

from app.config import config_by_name
# Importado com alias: o pacote app/scheduler/ (jobs em background) e
# esta variável (a instância do BackgroundScheduler) teriam o mesmo
# nome "scheduler" no namespace deste módulo, e o import do submódulo
# mais abaixo sobrescreveria a variável. O alias evita a colisão.
from app.extensions import db, migrate, jwt, cors, scheduler as agendador_scheduler


def create_app(config_name: str = "development") -> Flask:
    app = Flask(__name__)
    configuracao = config_by_name[config_name]
    if hasattr(configuracao, "validar"):
        configuracao.validar()
    app.config.from_object(configuracao)

    # Garante que logs INFO apareçam no console (ex.: mensagens de
    # WhatsApp simuladas em app/services/whatsapp_service.py). O
    # "force=True" sobrescreve qualquer configuração de logging que o
    # reloader do Flask/Werkzeug já tenha aplicado antes deste ponto.
    logging.basicConfig(
        level=logging.INFO if app.config["DEBUG"] else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
        force=True,
    )

    # --- Inicializa as extensões com esta instância do app ---
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    # CORS liberado para o domínio do frontend (React). Em produção,
    # troque FRONTEND_URL no .env pelo domínio real do seu site.
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    # Garante que todos os models estejam registrados no SQLAlchemy antes
    # de qualquer create_all()/migração.
    from app import models  # noqa: F401

    # --- Registra os blueprints (grupos de rotas) ---
    from app.routes.auth_routes import auth_bp
    from app.routes.salao_routes import salao_bp
    from app.routes.agendamento_routes import agendamento_bp
    from app.routes.pagamento_routes import pagamento_bp
    from app.routes.webhook_routes import webhook_bp
    from app.routes.cliente_routes import cliente_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(salao_bp, url_prefix="/api/saloes")
    app.register_blueprint(cliente_bp, url_prefix="/api/clientes")
    app.register_blueprint(agendamento_bp, url_prefix="/api/agendamentos")
    app.register_blueprint(pagamento_bp, url_prefix="/api/pagamentos")
    app.register_blueprint(webhook_bp, url_prefix="/api/webhooks")

    # --- Handlers de erro padronizados em JSON ---
    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return jsonify({"erro": "Recurso não encontrado."}), 404

    @app.errorhandler(500)
    def erro_interno(erro):
        app.logger.exception(erro)
        return jsonify({"erro": "Erro interno do servidor."}), 500

    @app.get("/api/health")
    def healthcheck():
        """Endpoint simples para checar se a API está no ar."""
        return jsonify({"status": "ok"})

    # --- Inicia o agendador de tarefas em background (APScheduler) ---
    # O "if not scheduler.running" evita iniciar duas vezes quando o
    # Flask recarrega o processo em modo debug (reloader cria 2 processos).
    from app.scheduler.jobs import registrar_jobs

    if app.config["SCHEDULER_ATIVO"] and not agendador_scheduler.running:
        registrar_jobs(agendador_scheduler, app)
        agendador_scheduler.start()

    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    return app
