"""liga a seguranca por linha (RLS) em todas as tabelas

Revision ID: b7c2e41d9a55
Revises: a1f3c9d27b10
Create Date: 2026-10-31 18:00:00

No Supabase, toda tabela do schema "public" fica exposta numa API REST
automática (PostgREST), acessível com a chave pública "anon". Como este
sistema só acessa o banco pelo backend Flask (que conecta como "postgres" e
ignora o RLS), ligamos o RLS SEM nenhuma política: assim a API REST do
Supabase não consegue ler nem gravar nada, e o backend continua igual.

Em um PostgreSQL comum (desenvolvimento local) isso não muda nada: o
dono das tabelas também ignora o RLS.

IMPORTANTE: tabelas criadas em migrações futuras precisam do mesmo comando
(ou basta rodar esta lógica de novo) — veja backend/README no projeto.
"""
from alembic import op


revision = 'b7c2e41d9a55'
down_revision = 'a1f3c9d27b10'
branch_labels = None
depends_on = None

_PERCORRE_TABELAS = """
DO $$
DECLARE tabela text;
BEGIN
    FOR tabela IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I {acao} ROW LEVEL SECURITY', tabela);
    END LOOP;
END $$;
"""


def upgrade():
    op.execute(_PERCORRE_TABELAS.format(acao="ENABLE"))


def downgrade():
    op.execute(_PERCORRE_TABELAS.format(acao="DISABLE"))
