# -*- coding: utf-8 -*-
"""
Configurações da aplicação, lidas a partir de variáveis de ambiente.

Nunca colocamos segredos (senhas, chaves de API) direto no código-fonte.
Em desenvolvimento, essas variáveis vêm do arquivo backend/.env (que é
carregado pelo python-dotenv em run.py) e NUNCA deve ser commitado no
Git — apenas o .env.example, que serve de modelo.
"""

import os
from datetime import timedelta

# Carrega o arquivo .env (se existir) para as variáveis de ambiente do
# processo. Em produção (ex.: servidor real), essas variáveis normalmente
# já vêm configuradas na infraestrutura, e o .env nem precisa existir.
from dotenv import load_dotenv

load_dotenv()


def _env_bool(nome, padrao=False):
    """Converte uma variável de ambiente em booleano (aceita '1', 'true', 'yes')."""
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Configuração base, compartilhada por todos os ambientes."""

    # --- Segurança / Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")

    # --- Banco de dados (PostgreSQL) ---
    # Formato esperado: postgresql://usuario:senha@host:porta/nome_do_banco
    # Usamos o driver psycopg (v3), daí o prefixo "postgresql+psycopg://".
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/salao_saas",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- JWT (autenticação) ---
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "troque-esta-chave-jwt-tambem")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "12"))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "30"))
    )

    # --- Frontend (usado para montar links em mensagens e CORS) ---
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # --- Mercado Pago ---
    # Access Token e Public Key de teste (sandbox) ou produção, obtidos em
    # https://www.mercadopago.com.br/developers/panel
    MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
    MERCADOPAGO_PUBLIC_KEY = os.getenv("MERCADOPAGO_PUBLIC_KEY", "")
    # Chave secreta usada para validar a assinatura (HMAC) dos webhooks do
    # Mercado Pago. Fica disponível no mesmo painel de desenvolvedor, em
    # "Webhooks" -> "Assinatura secreta".
    MERCADOPAGO_WEBHOOK_SECRET = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "")
    # Valor cobrado mensalmente do salão pela plataforma (em reais).
    PLATFORM_SUBSCRIPTION_PRICE = float(
        os.getenv("PLATFORM_SUBSCRIPTION_PRICE", "99.90")
    )
    # URL pública (ex.: via ngrok em dev) que o Mercado Pago vai chamar
    # para notificar eventos de pagamento/assinatura.
    MERCADOPAGO_WEBHOOK_URL = os.getenv(
        "MERCADOPAGO_WEBHOOK_URL", "http://localhost:5000/api/webhooks/mercadopago"
    )

    # --- WhatsApp ---
    # Qual provedor está sendo usado: "meta_cloud_api" (WhatsApp Business
    # Cloud API oficial da Meta) ou "evolution_api" (Evolution API,
    # open-source, comum em projetos brasileiros por não exigir aprovação
    # do WhatsApp/Meta). O código em whatsapp_service.py lê essa variável
    # para decidir qual integração usar — para trocar de provedor basta
    # mudar esta variável e as credenciais correspondentes, sem alterar
    # o resto da aplicação (routes, models etc.).
    WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "evolution_api")

    # Credenciais da Meta Cloud API (https://developers.facebook.com/docs/whatsapp)
    WHATSAPP_META_TOKEN = os.getenv("WHATSAPP_META_TOKEN", "")
    WHATSAPP_META_PHONE_NUMBER_ID = os.getenv("WHATSAPP_META_PHONE_NUMBER_ID", "")

    # Credenciais da Evolution API (https://doc.evolution-api.com)
    WHATSAPP_EVOLUTION_BASE_URL = os.getenv(
        "WHATSAPP_EVOLUTION_BASE_URL", "http://localhost:8080"
    )
    WHATSAPP_EVOLUTION_INSTANCE = os.getenv("WHATSAPP_EVOLUTION_INSTANCE", "salao-saas")
    WHATSAPP_EVOLUTION_API_KEY = os.getenv("WHATSAPP_EVOLUTION_API_KEY", "")

    # Se true, as mensagens de WhatsApp só são impressas no console em vez
    # de enviadas de verdade. Útil para desenvolver sem gastar créditos ou
    # sem ter uma instância de WhatsApp configurada ainda.
    WHATSAPP_MODO_SIMULACAO = _env_bool("WHATSAPP_MODO_SIMULACAO", True)

    # --- Agendamento (regras de negócio) ---
    # Quantos dias de antecedência mínima/máxima um cliente pode agendar.
    AGENDAMENTO_ANTECEDENCIA_MAXIMA_DIAS = int(
        os.getenv("AGENDAMENTO_ANTECEDENCIA_MAXIMA_DIAS", "60")
    )


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/salao_saas_test",
    )
    WHATSAPP_MODO_SIMULACAO = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
