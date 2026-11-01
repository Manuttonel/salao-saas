# -*- coding: utf-8 -*-
"""
Models do salão: Salao, Servico (procedimentos), DiaAgenda e
SalaoAdministrador.

Salao representa a barbearia/salão de beleza. Servico é o catálogo de
procedimentos (corte, escova, unhas, limpeza de pele...) — a duração de
cada um é o que a lógica de agendamento usa para calcular o horário de
término e evitar conflitos (veja app/services/agendador_service.py).

O "Marcar Avaliação" é um Servico especial (eh_avaliacao=True) criado
automaticamente em todo salão. Como é um Servico comum, o administrador
escolhe a duração dele (normalmente bem menor que a de um procedimento).

DiaAgenda guarda as exceções de calendário que o administrador marca:
"neste dia abro (talvez em horário diferente)" ou "neste dia fecho".

SalaoAdministrador liga usuários extras (papel "administrador") ao salão,
permitindo mais de uma pessoa gerenciar o mesmo estabelecimento.
"""

import uuid

from app.extensions import db

# Categorias de procedimento (chave -> rótulo). A chave é o que fica no banco.
CATEGORIAS_SERVICO = {
    "cabelo": "Cabelo",
    "unhas": "Unhas",
    "estetica": "Estética",
    "barba": "Barba",
    "outros": "Outros",
    "avaliacao": "Avaliação",
}

NOME_SERVICO_AVALIACAO = "Marcar Avaliação"
DURACAO_PADRAO_AVALIACAO = 20  # minutos; o administrador pode alterar


class Salao(db.Model):
    __tablename__ = "saloes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dono_id = db.Column(db.String(36), db.ForeignKey("usuarios.id"), nullable=False)

    nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    endereco = db.Column(db.String(255), nullable=True)

    # Horário de funcionamento padrão do salão.
    horario_abertura = db.Column(db.Time, nullable=False)
    horario_fechamento = db.Column(db.Time, nullable=False)

    # Dias da semana em que o salão funciona (0=segunda ... 6=domingo).
    dias_funcionamento = db.Column(db.JSON, nullable=False, default=lambda: [0, 1, 2, 3, 4, 5])

    # Se True, o salão só atende nos dias que o administrador marcou
    # explicitamente como disponíveis no calendário (ignora a semana-padrão).
    somente_dias_marcados = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.false()
    )

    # Nome da instância do WhatsApp (Evolution API) deste salão. Vazio = usa
    # a instância global definida no .env.
    whatsapp_instancia = db.Column(db.String(80), nullable=True)

    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    dono = db.relationship("Usuario", back_populates="saloes")
    administradores_vinculos = db.relationship(
        "SalaoAdministrador", back_populates="salao", cascade="all, delete-orphan"
    )
    profissionais = db.relationship(
        "Profissional", back_populates="salao", cascade="all, delete-orphan"
    )
    servicos = db.relationship("Servico", back_populates="salao", cascade="all, delete-orphan")
    clientes = db.relationship("Cliente", back_populates="salao")
    dias_agenda = db.relationship("DiaAgenda", back_populates="salao", cascade="all, delete-orphan")
    agendamentos = db.relationship("Agendamento", back_populates="salao")
    assinatura = db.relationship(
        "Assinatura", back_populates="salao", uselist=False, cascade="all, delete-orphan"
    )

    def esta_com_acesso_liberado(self) -> bool:
        """
        Regra de negócio: o painel só fica liberado se a assinatura da
        plataforma estiver em dia. Sem assinatura ainda (período de teste)
        ou aprovada = liberado.
        """
        if self.assinatura is None:
            return True
        return self.assinatura.esta_ativa()

    def administradores(self) -> list:
        """Dono + administradores convidados."""
        return [self.dono] + [v.usuario for v in self.administradores_vinculos if v.usuario.ativo]

    def eh_administrador(self, usuario) -> bool:
        if usuario is None:
            return False
        if usuario.id == self.dono_id:
            return True
        return any(v.usuario_id == usuario.id for v in self.administradores_vinculos)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dono_id": self.dono_id,
            "nome": self.nome,
            "telefone": self.telefone,
            "endereco": self.endereco,
            "horario_abertura": self.horario_abertura.strftime("%H:%M"),
            "horario_fechamento": self.horario_fechamento.strftime("%H:%M"),
            "dias_funcionamento": self.dias_funcionamento,
            "somente_dias_marcados": bool(self.somente_dias_marcados),
            "whatsapp_instancia": self.whatsapp_instancia,
            "acesso_liberado": self.esta_com_acesso_liberado(),
        }


class SalaoAdministrador(db.Model):
    """Vínculo entre um salão e um usuário administrador (além do dono)."""

    __tablename__ = "salao_administradores"
    __table_args__ = (db.UniqueConstraint("salao_id", "usuario_id", name="uq_salao_admin"),)

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    salao_id = db.Column(db.String(36), db.ForeignKey("saloes.id"), nullable=False)
    usuario_id = db.Column(db.String(36), db.ForeignKey("usuarios.id"), nullable=False)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    salao = db.relationship("Salao", back_populates="administradores_vinculos")
    usuario = db.relationship("Usuario", back_populates="vinculos_admin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario_id": self.usuario_id,
            "nome": self.usuario.nome,
            "email": self.usuario.email,
            "telefone": self.usuario.telefone,
            "eh_dono": False,
        }


class Servico(db.Model):
    """Um procedimento oferecido pelo salão (corte, unhas, limpeza de pele...)."""

    __tablename__ = "servicos"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    salao_id = db.Column(db.String(36), db.ForeignKey("saloes.id"), nullable=False)

    nome = db.Column(db.String(120), nullable=False)
    categoria = db.Column(db.String(30), nullable=False, default="outros", server_default="outros")
    descricao = db.Column(db.String(300), nullable=True)
    duracao_minutos = db.Column(db.Integer, nullable=False)
    preco = db.Column(db.Numeric(10, 2), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    # True apenas para o procedimento especial "Marcar Avaliação".
    eh_avaliacao = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.false()
    )

    salao = db.relationship("Salao", back_populates="servicos")
    agendamentos = db.relationship("Agendamento", back_populates="servico")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "salao_id": self.salao_id,
            "nome": self.nome,
            "categoria": self.categoria,
            "categoria_nome": CATEGORIAS_SERVICO.get(self.categoria, "Outros"),
            "descricao": self.descricao,
            "duracao_minutos": self.duracao_minutos,
            "preco": float(self.preco),
            "ativo": self.ativo,
            "eh_avaliacao": bool(self.eh_avaliacao),
        }


class DiaAgenda(db.Model):
    """
    Exceção de calendário marcada pelo administrador para uma data
    específica:
      - aberto=True  -> o salão atende neste dia (mesmo que a semana-padrão
                        diga que não), opcionalmente em horário próprio;
      - aberto=False -> o salão NÃO atende neste dia (feriado, folga...).
    Datas sem registro seguem a regra geral do salão.
    """

    __tablename__ = "dias_agenda"
    __table_args__ = (db.UniqueConstraint("salao_id", "data", name="uq_dia_agenda_salao_data"),)

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    salao_id = db.Column(db.String(36), db.ForeignKey("saloes.id"), nullable=False, index=True)
    data = db.Column(db.Date, nullable=False)
    aberto = db.Column(db.Boolean, nullable=False, default=True)
    hora_inicio = db.Column(db.Time, nullable=True)
    hora_fim = db.Column(db.Time, nullable=True)
    motivo = db.Column(db.String(120), nullable=True)

    salao = db.relationship("Salao", back_populates="dias_agenda")

    def to_dict(self) -> dict:
        return {
            "data": self.data.isoformat(),
            "aberto": self.aberto,
            "hora_inicio": self.hora_inicio.strftime("%H:%M") if self.hora_inicio else None,
            "hora_fim": self.hora_fim.strftime("%H:%M") if self.hora_fim else None,
            "motivo": self.motivo,
        }
