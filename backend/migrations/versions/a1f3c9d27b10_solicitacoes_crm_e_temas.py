"""solicitacoes, crm de clientes, administradores, calendario, bot e temas

Revision ID: a1f3c9d27b10
Revises: ddbedcae0bdc
Create Date: 2026-10-31 12:00:00

Escrita à mão (o autogenerate do Alembic não enxerga novos valores de enum
nem faz o preenchimento dos dados que já existem).
"""
import uuid

from alembic import op
import sqlalchemy as sa


revision = 'a1f3c9d27b10'
down_revision = 'ddbedcae0bdc'
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. Novos valores de enum -------------------------------------------
    # ALTER TYPE ... ADD VALUE não pode rodar dentro de uma transação.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE papelusuario ADD VALUE IF NOT EXISTS 'ADMINISTRADOR'")
        op.execute("ALTER TYPE statusagendamento ADD VALUE IF NOT EXISTS 'RECUSADO'")

    # --- 2. usuarios: preferência de tema -----------------------------------
    op.add_column('usuarios', sa.Column('tema', sa.String(length=20), nullable=False, server_default='unisex'))
    op.add_column('usuarios', sa.Column('cor_primaria', sa.String(length=7), nullable=True))

    # --- 3. saloes ----------------------------------------------------------
    op.add_column('saloes', sa.Column('whatsapp_instancia', sa.String(length=80), nullable=True))
    op.add_column('saloes', sa.Column('somente_dias_marcados', sa.Boolean(), nullable=False, server_default=sa.false()))

    # --- 4. servicos (procedimentos) ----------------------------------------
    op.add_column('servicos', sa.Column('categoria', sa.String(length=30), nullable=False, server_default='outros'))
    op.add_column('servicos', sa.Column('descricao', sa.String(length=300), nullable=True))
    op.add_column('servicos', sa.Column('eh_avaliacao', sa.Boolean(), nullable=False, server_default=sa.false()))

    # --- 5. profissionais: podem existir sem login --------------------------
    op.add_column('profissionais', sa.Column('nome', sa.String(length=120), nullable=True))
    op.alter_column('profissionais', 'usuario_id', existing_type=sa.String(length=36), nullable=True)
    op.execute(sa.text(
        "UPDATE profissionais p SET nome = u.nome FROM usuarios u WHERE p.usuario_id = u.id"
    ))

    # --- 6. clientes: ficha por salão (CRM) ---------------------------------
    op.add_column('clientes', sa.Column('salao_id', sa.String(length=36), nullable=True))
    op.add_column('clientes', sa.Column('nome', sa.String(length=120), nullable=True))
    op.add_column('clientes', sa.Column('telefone', sa.String(length=20), nullable=True))
    op.add_column('clientes', sa.Column('email', sa.String(length=160), nullable=True))
    op.add_column('clientes', sa.Column('observacoes', sa.Text(), nullable=True))
    op.add_column('clientes', sa.Column('origem', sa.String(length=20), nullable=False, server_default='manual'))
    op.add_column('clientes', sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column('clientes', 'usuario_id', existing_type=sa.String(length=36), nullable=True)
    # Antes: 1 cliente por usuário. Agora: 1 ficha por usuário POR SALÃO.
    op.execute("ALTER TABLE clientes DROP CONSTRAINT IF EXISTS clientes_usuario_id_key")
    op.create_foreign_key('fk_clientes_salao_id', 'clientes', 'saloes', ['salao_id'], ['id'])
    op.create_index('ix_clientes_salao_id', 'clientes', ['salao_id'])
    op.create_index('ix_clientes_telefone', 'clientes', ['telefone'])

    # Preenche as fichas antigas com os dados do usuário e o salão onde já agendaram.
    op.execute(sa.text(r"""
        UPDATE clientes c
        SET nome = u.nome,
            email = u.email,
            origem = 'app',
            telefone = CASE
                WHEN length(regexp_replace(u.telefone, '\D', '', 'g')) IN (10, 11)
                    THEN '55' || regexp_replace(u.telefone, '\D', '', 'g')
                ELSE regexp_replace(u.telefone, '\D', '', 'g')
            END
        FROM usuarios u
        WHERE c.usuario_id = u.id
    """))
    op.execute(sa.text("""
        UPDATE clientes c
        SET salao_id = (
            SELECT a.salao_id FROM agendamentos a
            WHERE a.cliente_id = c.id ORDER BY a.inicio LIMIT 1
        )
        WHERE c.salao_id IS NULL
    """))

    # --- 7. agendamentos: fluxo de solicitação ------------------------------
    op.add_column('agendamentos', sa.Column('origem', sa.String(length=20), nullable=False, server_default='web'))
    op.add_column('agendamentos', sa.Column('motivo_recusa', sa.String(length=300), nullable=True))
    op.add_column('agendamentos', sa.Column('respondido_por_id', sa.String(length=36), nullable=True))
    op.add_column('agendamentos', sa.Column('respondido_em', sa.DateTime(), nullable=True))
    op.create_foreign_key('fk_agendamentos_respondido_por', 'agendamentos', 'usuarios', ['respondido_por_id'], ['id'])

    # --- 8. tabelas novas ---------------------------------------------------
    op.create_table('salao_administradores',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('salao_id', sa.String(length=36), nullable=False),
        sa.Column('usuario_id', sa.String(length=36), nullable=False),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['salao_id'], ['saloes.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('salao_id', 'usuario_id', name='uq_salao_admin'),
    )
    op.create_table('dias_agenda',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('salao_id', sa.String(length=36), nullable=False),
        sa.Column('data', sa.Date(), nullable=False),
        sa.Column('aberto', sa.Boolean(), nullable=False),
        sa.Column('hora_inicio', sa.Time(), nullable=True),
        sa.Column('hora_fim', sa.Time(), nullable=True),
        sa.Column('motivo', sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(['salao_id'], ['saloes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('salao_id', 'data', name='uq_dia_agenda_salao_data'),
    )
    op.create_index('ix_dias_agenda_salao_id', 'dias_agenda', ['salao_id'])
    op.create_table('conversas_whatsapp',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('salao_id', sa.String(length=36), nullable=False),
        sa.Column('telefone', sa.String(length=20), nullable=False),
        sa.Column('estado', sa.String(length=30), nullable=False),
        sa.Column('dados', sa.JSON(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['salao_id'], ['saloes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('salao_id', 'telefone', name='uq_conversa_salao_telefone'),
    )

    # --- 9. Salões que já existem ganham "Marcar Avaliação" e um profissional padrão
    conexao = op.get_bind()
    for salao_id, nome_dono in conexao.execute(sa.text(
        "SELECT s.id, u.nome FROM saloes s JOIN usuarios u ON u.id = s.dono_id"
    )).fetchall():
        conexao.execute(sa.text(
            "INSERT INTO servicos (id, salao_id, nome, categoria, descricao, duracao_minutos, preco, ativo, eh_avaliacao) "
            "VALUES (:id, :salao, 'Marcar Avaliação', 'avaliacao', "
            "'Conversa rápida para avaliar o que você precisa.', 20, 0, true, true)"
        ), {"id": str(uuid.uuid4()), "salao": salao_id})

        tem_profissional = conexao.execute(
            sa.text("SELECT count(*) FROM profissionais WHERE salao_id = :salao"), {"salao": salao_id}
        ).scalar()
        if not tem_profissional:
            conexao.execute(sa.text(
                "INSERT INTO profissionais (id, salao_id, nome, ativo) VALUES (:id, :salao, :nome, true)"
            ), {"id": str(uuid.uuid4()), "salao": salao_id, "nome": nome_dono})


def downgrade():
    # Os valores novos dos enums (ADMINISTRADOR, RECUSADO) não podem ser
    # removidos do PostgreSQL; ficam no tipo, sem uso.
    op.drop_table('conversas_whatsapp')
    op.drop_index('ix_dias_agenda_salao_id', table_name='dias_agenda')
    op.drop_table('dias_agenda')
    op.drop_table('salao_administradores')

    op.drop_constraint('fk_agendamentos_respondido_por', 'agendamentos', type_='foreignkey')
    op.drop_column('agendamentos', 'respondido_em')
    op.drop_column('agendamentos', 'respondido_por_id')
    op.drop_column('agendamentos', 'motivo_recusa')
    op.drop_column('agendamentos', 'origem')

    op.drop_index('ix_clientes_telefone', table_name='clientes')
    op.drop_index('ix_clientes_salao_id', table_name='clientes')
    op.drop_constraint('fk_clientes_salao_id', 'clientes', type_='foreignkey')
    for coluna in ('ativo', 'origem', 'observacoes', 'email', 'telefone', 'nome', 'salao_id'):
        op.drop_column('clientes', coluna)

    op.drop_column('profissionais', 'nome')
    op.drop_column('servicos', 'eh_avaliacao')
    op.drop_column('servicos', 'descricao')
    op.drop_column('servicos', 'categoria')
    op.drop_column('saloes', 'somente_dias_marcados')
    op.drop_column('saloes', 'whatsapp_instancia')
    op.drop_column('usuarios', 'cor_primaria')
    op.drop_column('usuarios', 'tema')
